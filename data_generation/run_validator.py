#!/usr/bin/env python3
import os
import json
import time
import yaml  # Use PyYAML for gold data
from contextlib import contextmanager

from agentforge.agent import Agent
from checkpoint_manager import CheckpointManager
from agentforge.utils.parsing_processor import ParsingProcessor, ParsingError

@contextmanager
def timer(task_name, timings):
    """
    Context manager to measure elapsed time for a code block.
    """
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    timings[task_name] = elapsed

def sanitize_category(category):
    """Convert category string into a filesystem-safe format."""
    return category.replace(' ', '_').replace('/', '_')

class ValidatorManager:
    def __init__(
        self,
        gold_dir: str = "qas",                # Directory with gold QAs (YAML files)
        model_dir: str = "o7responses",         # Directory with model responses (JSON files)
        output_dir: str = "validator_outputs",
        checkpoint_file: str = "validator_checkpoint.json"
    ):
        """
        :param gold_dir: Directory with one YAML file per category, containing gold QAs.
        :param model_dir: Directory with one JSON file per category, containing model responses.
        :param output_dir: Directory in which to save validation results.
        :param checkpoint_file: File used to keep track of processed categories.
        """
        self.gold_dir = gold_dir
        self.model_dir = model_dir
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.checkpoint_file = checkpoint_file
        self.checkpoint_manager = CheckpointManager(self.checkpoint_file)
        self.processed_categories = self.checkpoint_manager.load()

        # Validator agent and YAML parser
        self.validator_agent = Agent("ValidatorAgent")
        self._parser = ParsingProcessor()

        # Timing information
        self.start_time = None
        self.timings = {}

    def start_time_counter(self):
        """Record the start time of the validation run."""
        self.start_time = time.perf_counter()
        start_human = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"\nValidation started at: {start_human}\n")

    def show_time_summary(self):
        """Display time tracking summary after run completes."""
        total_elapsed = time.perf_counter() - self.start_time
        print(f"\nTotal validation run time: {total_elapsed:.2f} seconds")
        print("Timing Summary:")
        for task, elapsed in self.timings.items():
            print(f" - {task}: {elapsed:.2f} seconds")

    def run(self):
        """
        Main method: iterate over gold QA files (YAML) in gold_dir,
        find corresponding model responses (JSON) in model_dir,
        validate each category, and save results.
        """
        self.start_time_counter()

        # Expect gold files to be YAML files
        gold_files = [f for f in os.listdir(self.gold_dir) if f.endswith(".yaml")]
        total_categories = len(gold_files)

        for idx, gold_filename in enumerate(gold_files, start=1):
            category_name = os.path.splitext(gold_filename)[0]

            if category_name in self.processed_categories:
                print(f"Skipping category '{category_name}' (already processed).")
                continue

            print(f"\nValidating category ({idx}/{total_categories}): '{category_name}'")

            gold_path = os.path.join(self.gold_dir, gold_filename)
            model_path = os.path.join(self.model_dir, f"{category_name}.json")
            if not os.path.exists(model_path):
                print(f"  No model response file found for '{category_name}'. Skipping.")
                continue

            with timer(f"{category_name}_validation", self.timings):
                self.process_category(category_name, gold_path, model_path)

            # Mark category as processed
            self.processed_categories.add(category_name)
            self.checkpoint_manager.save(self.processed_categories)

        self.show_time_summary()

    def process_category(self, category_name: str, gold_path: str, model_path: str):
        """
        Process one category: load gold QAs (YAML) and model responses (JSON),
        validate each question, and save the output.
        """
        gold_data = self.load_yaml(gold_path)
        model_data = self.load_json(model_path)
        if gold_data is None or model_data is None:
            print(f"  Could not load data for category '{category_name}'.")
            return

        # Skip category if counts don't match
        if len(gold_data) != len(model_data):
            print(f"  Mismatch in number of items for '{category_name}' "
                  f"(gold={len(gold_data)}, model={len(model_data)}) => Skipping.")
            return

        results = []
        for i, gold_item in enumerate(gold_data):
            question = gold_item.get("question", "")
            correct_answer = gold_item.get("answer", "")
            proof = gold_item.get("proof", "")

            model_item = model_data[i] if i < len(model_data) else {}
            model_answer = self.extract_model_answer(model_item)

            assessment, score = self.validate_question(
                question=question,
                correct_answer=correct_answer,
                proof=proof,
                given_answer=model_answer
            )

            results.append({
                "question": question,
                "correct_answer": correct_answer,
                "proof": proof,
                "given_answer": model_answer,
                "assessment": assessment,
                "score": score
            })

        output_file = os.path.join(self.output_dir, f"{sanitize_category(category_name)}.json")
        self.save_json(results, output_file)
        print(f"  Validator results saved to: {output_file}")

    def validate_question(self, question: str, correct_answer: str, proof: str, given_answer: str):
        """
        Calls the ValidatorAgent and parses its YAML output to return (assessment, score).
        """
        agent_output = self.validator_agent.run(
            question=question,
            correct_answer=correct_answer,
            proof=proof,
            given_answer=given_answer
        )
        return self.parse_validator_response(agent_output)

    def parse_validator_response(self, raw_text: str):
        """
        Uses ParsingProcessor to parse the YAML output from the validator agent.
        Expects keys: 'assessment' and 'score'.
        """
        try:
            parsed = self._parser.parse_by_format(raw_text, "yaml")
            assessment = parsed.get("assessment", "").strip()
            score = str(parsed.get("score", ""))
            return assessment, score
        except ParsingError as e:
            print(f"  [Warning] YAML parsing error: {e}")
            return raw_text.strip(), ""

    def extract_model_answer(self, model_item) -> str:
        """
        Extracts the final answer from a model response item.
        The model response is now a list of steps (thought, theory, reason, reflect, generate, etc.),
        and we want the final answer from the last 'generate' step.
        """
        if isinstance(model_item, list):
            # Iterate in reverse order to find the last step with 'generate'
            for step in reversed(model_item):
                if "generate" in step:
                    generate_data = step["generate"]
                    # If it's a dict, extract the 'final_response'
                    if isinstance(generate_data, dict):
                        return generate_data.get("final_response", "").strip()

                    return str(generate_data).strip()
            # Fallback if no 'generate' step is found
            return ""
        return ""

    def load_yaml(self, path: str):
        """Utility to load a YAML file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"  Error loading YAML from {path}: {e}")
            return None

    def load_json(self, path: str):
        """Utility to load a JSON file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"  Error loading JSON from {path}: {e}")
            return None

    def save_json(self, data, path: str):
        """Utility to save data as pretty-printed JSON."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"  Error saving JSON to {path}: {e}")


if __name__ == "__main__":
    manager = ValidatorManager(
        gold_dir="qas",             # Or wherever your gold QAs now live
        model_dir="o7responses",    # Directory with model responses
        output_dir="validator_outputs",
        checkpoint_file="validator_checkpoint.json"
    )
    manager.run()
