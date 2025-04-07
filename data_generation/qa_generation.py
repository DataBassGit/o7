import os
import time
import yaml
from contextlib import contextmanager
from agentforge.agent import Agent
from checkpoint_manager import CheckpointManager
from agentforge.utils.parsing_processor import ParsingProcessor


@contextmanager
def timer(task_name, timings):
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    timings[task_name] = elapsed


class QAGenManager:
    def __init__(self, categories_file='../categories.txt', checkpoint_file="qa_gen_checkpoint.json",
                 output_dir='qas', num_questions=4, max_validation_attempts=2, max_generation_attempts=2):
        self.categories_file = categories_file
        self.checkpoint_file = checkpoint_file
        self.output_dir = output_dir
        self.num_questions = num_questions
        self.max_validation_attempts = max_validation_attempts
        self.max_generation_attempts = max_generation_attempts

        self._parser = ParsingProcessor()
        self.checkpoint_manager = CheckpointManager(checkpoint_file)
        self.processed_categories = self.checkpoint_manager.load()
        self.qa_gen_agent = Agent('QAGenAgent')
        self.qa_validator_agent = Agent('QAValidator')
        self.categories = self.load_categories()
        self.start_time = None
        self.timings = {}  # Dictionary to store timing information

    def load_categories(self):
        with open(self.categories_file, 'r') as file:
            return [line.strip() for line in file if line.strip()]

    @staticmethod
    def sanitize_category(category):
        return category.replace(' ', '_').replace('/', '_')

    def generate_qa_pair(self, category, previous_questions, previous_question=None, previous_proof=None,
                         previous_answer=None, analysis=None, recommended_changes=None):
        """Generate a single QA pair with optional revision parameters"""
        # Base parameters for all requests
        kwargs = {
            'topic': category,
            'previous_questions': previous_questions.strip() if previous_questions else ""
        }

        # Check if all revision parameters are provided
        is_revision = all([
            previous_question is not None,
            previous_proof is not None,
            previous_answer is not None,
            analysis is not None,
            recommended_changes is not None
        ])

        # Only include revision parameters for an actual revision
        if is_revision:
            kwargs.update({
                'previous_question': previous_question,
                'previous_proof': previous_proof,
                'previous_answer': previous_answer,
                'analysis': analysis,
                'recommended_changes': recommended_changes
            })

        result = self.qa_gen_agent.run(**kwargs)
        # First parse the YAML using the standard parser
        parsed_data = self._parser.parse_by_format(result, 'yaml', ['~~~', '```'])
        # Then normalize the data to ensure consistent format
        return self._normalize_qa_data(parsed_data, 'qa_gen')

    @staticmethod
    def _normalize_qa_data(qa_data, schema_type=None):
        """
        Normalize the parsed QA data to ensure consistent formatting.
        This helps prevent inconsistencies from the parsing stage.
        
        Args:
            qa_data: The parsed QA data to normalize
            schema_type: The type of schema to validate against (e.g., 'qa_gen', 'validation')
                         If None, will attempt to auto-detect based on keys present
        """
        # Define known schemas
        SCHEMAS = {
            'qa_gen': {'required': ['question', 'proof', 'answer']},
            'validation': {'required': ['validity', 'analysis', 'recommended_changes']}
        }
        
        if qa_data is None:
            print("  Warning: Parsed QA data is None, returning empty dict")
            return {}

        if not isinstance(qa_data, dict):
            print(f"  Warning: Parsed QA data is not a dict but {type(qa_data)}, attempting conversion")
            try:
                # Try to convert to dict if it's some other type
                qa_data = dict(qa_data)
            except:
                print("  Error: Could not convert to dict, returning empty dict")
                return {}

        # Auto-detect schema if not specified
        if schema_type is None:
            # If schema_type is None, ensure that qa_data is a valid dict
            if not isinstance(qa_data, dict):
                print("  Error: Parsed QA data is not a dict, returning empty dict")
                return {}
            
            return qa_data

        normalized = {}
        for key, value in qa_data.items():
            # Skip None values
            if value is None:
                continue

            # Strip code blocks if they somehow got through parsing
            str_value = str(value).strip()
            if str_value.startswith("```") and str_value.endswith("```"):
                # Extract content from code block
                lines = str_value.split("\n")
                if len(lines) > 2:
                    str_value = "\n".join(lines[1:-1]).strip()

            # Store the normalized value
            normalized[key] = str_value

        # Check for required keys and provide defaults if missing
        required_keys = SCHEMAS.get(schema_type, {}).get('required', [])
        for required_key in required_keys:
            if required_key not in normalized:
                normalized[required_key] = f"Missing {required_key}"
                print(f"  Warning: Required key '{required_key}' was missing from {schema_type} data, adding placeholder")

        return normalized

    def validate_qa_pair(self, qa_pair, previous_questions):
        """Validate a QA pair using the QAValidator agent"""
        max_retries = 3
        retry_delay = 2

        for retry in range(max_retries):
            try:
                validation_result = self.qa_validator_agent.run(
                    previous_question=qa_pair.get('question', ''),
                    previous_proof=qa_pair.get('proof', ''),
                    previous_answer=qa_pair.get('answer', ''),
                    previous_questions=previous_questions
                )

                validation_data = self._parser.parse_by_format(validation_result, 'yaml', ['~~~', '```'])
                # Normalize the validation data
                validation_data = self._normalize_qa_data(validation_data, 'validation')
                return validation_data
            except Exception as e:
                # If this is the last retry, we propagate the error upward
                if retry == max_retries - 1:
                    print(f"  Validation failed after {max_retries} attempts: {e}")
                    return {'validity': 'error', 'analysis': f'Error: {e}',
                            'recommended_changes': 'Could not validate due to API error'}

                # Otherwise, we retry with exponential backoff
                delay = retry_delay * (2 ** retry)
                print(f"  Validation error: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)

    def generate_and_validate_qa_pair(self, category, previous_questions):
        """Generate and validate a single QA pair with retry logic"""
        for gen_attempt in range(self.max_generation_attempts):
            # For each new generation attempt, start fresh with no revision parameters
            qa_pair = self.generate_qa_pair(category, previous_questions)

            # Try to validate the generated QA pair
            for val_attempt in range(self.max_validation_attempts):
                validation_result = self.validate_qa_pair(qa_pair, previous_questions)
                validity = validation_result.get('validity', '').strip().lower()

                if validity == 'valid':
                    # Success - return the valid QA pair
                    return qa_pair, True

                if validity == 'invalid' and val_attempt < self.max_validation_attempts - 1:
                    # Invalid pair, attempt revision with the current qa_pair's data
                    print(f"  Revising QA pair (validation attempt {val_attempt + 1})")
                    qa_pair = self.generate_qa_pair(
                        category,
                        previous_questions,
                        qa_pair.get('question', ''),
                        qa_pair.get('proof', ''),
                        qa_pair.get('answer', ''),
                        validation_result.get('analysis', ''),
                        validation_result.get('recommended_changes', '')
                    )
                else:
                    # Either validation failed with an error or 
                    # we've reached our max revision attempts for an invalid pair
                    break

            print(f"  Failed to validate QA pair (generation attempt {gen_attempt + 1})")
            if gen_attempt < self.max_generation_attempts - 1:
                print(f"  Trying to generate a new QA pair from scratch")

        # If we reach here, we couldn't generate a valid QA pair after all attempts
        # Return the pair but mark it as invalid
        return qa_pair, False

    def generate_qa_pairs_for_category(self, category):
        qa_pairs = []
        previous_questions = []

        idx = 0
        while idx < self.num_questions:
            task_name = f"question_{idx + 1}_generation"
            with timer(task_name, self.timings):
                print(f"  Generating QA pair {idx + 1}/{self.num_questions}")
                prev_qs = "\n".join(previous_questions)

                # Clear attempt to generate and validate a QA pair
                qa_pair, is_valid = self.generate_and_validate_qa_pair(category, prev_qs)

                if is_valid:
                    # Format the question to add to previous questions
                    qa_pairs.append(qa_pair)
                    new_question = f'- {qa_pair.get("question", "").strip()}\n'
                    previous_questions.append(new_question)
                    print(f"  Successfully generated and validated QA pair {idx + 1}")
                    idx += 1
                else:
                    print(f"  Failed to generate a valid QA pair {idx + 1} after all attempts")
                    print(f"  Skipping this question and continuing to the next one")

        # If we couldn't generate all requested questions, log a warning
        if len(qa_pairs) < self.num_questions:
            print(f"  Warning: Only generated {len(qa_pairs)}/{self.num_questions} valid QA pairs")

        return qa_pairs

    def save_qa_pairs(self, category, qa_pairs):
        os.makedirs(self.output_dir, exist_ok=True)
        sanitized = self.sanitize_category(category)
        output_file = os.path.join(self.output_dir, f"{sanitized}.yaml")

        # Pre-process the qa_pairs to ensure each field uses block scalar format
        processed_qa_pairs = []
        for qa_pair in qa_pairs:
            processed_pair = {}
            for key, value in qa_pair.items():
                # Ensure the value is a string and not empty
                if value is not None:
                    value = str(value).rstrip()
                    processed_pair[key] = value
            processed_qa_pairs.append(processed_pair)

        # Create a custom YAML dumper to ensure consistent formatting
        class BlockStyleDumper(yaml.SafeDumper):
            def represent_scalar(self, tag, value, style=None):
                # Force block scalar style for all string values
                if tag == 'tag:yaml.org,2002:str':
                    style = '|'
                return super().represent_scalar(tag, value, style)

        # Write the YAML file with our custom dumper
        with open(output_file, 'w') as f:
            yaml.dump(processed_qa_pairs, f,
                      Dumper=BlockStyleDumper,
                      sort_keys=False,
                      default_flow_style=False,
                      allow_unicode=True)

        return output_file, []

    def update_checkpoint(self, category):
        self.processed_categories.add(category)
        # Retrieve the processing time for the category from self.timings.
        cat_time = self.timings.get(f"{category}_processing", 0)
        try:
            # Save both the processed set and the timing information.
            self.checkpoint_manager.save(self.processed_categories, timings={category: cat_time})
        except Exception as e:
            print(f"  Warning: Error updating checkpoint for '{category}': {e}")
            # Try without timings as a fallback
            try:
                self.checkpoint_manager.save(self.processed_categories)
            except Exception as e2:
                print(f"  Error: Could not save checkpoint at all: {e2}")

    def process_category(self, category):
        with timer(f"{category}_processing", self.timings):
            print(f"Generating QA pairs for category: {category}")
            qa_pairs = self.generate_qa_pairs_for_category(category)
            output_file, _ = self.save_qa_pairs(category, qa_pairs)
            print(f"Saved QA pairs for '{category}' in file: {output_file}")
            self.update_checkpoint(category)

    def process_category_time(self, category):
        # Retrieve and print the processing time for the current category.
        cat_time = self.timings.get(f"{category}_processing")
        if cat_time is not None:
            print(f"Category '{category}' processed in {cat_time:.2f} seconds.\n")

    def process_all_categories(self):
        for category in self.categories:
            if category in self.processed_categories:
                print(f"Skipping {category} (already processed).")
                continue
            try:
                self.process_category(category)
                self.process_category_time(category)
            except Exception as e:
                print(f"Error generating QA pairs for '{category}': {e}")

    def show_time_summary(self):
        total_elapsed = time.perf_counter() - self.start_time
        print(f"Total run time: {total_elapsed:.2f} seconds")
        print("Timing Summary:")
        for task, elapsed in self.timings.items():
            print(f" - {task}: {elapsed:.2f} seconds")

    def start_time_counter(self):
        # Mark the start of the run.
        self.start_time = time.perf_counter()
        start_human = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"\nRun started at: {start_human}\n")

    def run(self):
        self.start_time_counter()
        try:
            self.process_all_categories()
        except KeyboardInterrupt:
            print("Keyboard interrupt detected. Exiting gracefully!!!\n")
        self.show_time_summary()


if __name__ == '__main__':
    manager = QAGenManager()
    manager.run()
