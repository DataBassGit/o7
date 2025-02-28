#!/usr/bin/env python3
import os
import json
import yaml
from collections import OrderedDict

# Configuration: set your system prompt and score threshold here.
SYSTEM_PROMPT = (
    "You are a thinking agent responsible for developing a detailed, step-by-step chain-of-thought "
    "in response to a request. Your task is to break down the question into a structured reasoning process. "
    "Incorporate feedback to refine your reasoning."
)
SCORE_THRESHOLD = 70


def sanitize_category(filename):
    """
    Convert a filename (without extension) into a human-friendly category.
    For example, "Astro-ph_CO.yaml" becomes "Astro-ph CO".
    """
    base = os.path.splitext(filename)[0]
    return base.replace('_', ' ').replace('.', ' ')


def thought_flow_to_xml(thought_flow):
    """
    Convert the chain-of-thought (cog_flow) into an XML string.
    The thought_flow is expected to be a list of dictionaries where each dictionary
    has a single key (e.g., "thought", "theory", "reason", "reflect", "generate")
    whose value is another dictionary. The mapping below is updated to reflect
    the current output keys.
    """
    mapping = {
        ('thought', 'contextual_analysis'): 'analysis',
        ('thought', 'emotions'): 'emotions',
        ('thought', 'thoughts'): 'thoughts',
        ('thought', 'impression'): 'impression',

        ('theory', 'mindset'): 'mindset',
        ('theory', 'insight'): 'insight',

        ('reason', 'initial_understanding'): 'understanding',
        ('reason', 'reasoning'): 'reasoning',
        ('reason', 'synthesis'): 'cohesion',

        ('reflect', 'choice'): 'decision',
        ('reflect', 'reasoning'): 'reflection',
        ('reflect', 'stewardship'): 'steering',

        ('generate', 'introspection'): 'introspection',
        ('generate', 'final_response'): 'response'
    }

    xml_lines = []
    current_tag = None
    current_contents = []

    for item in thought_flow:
        for outer_key, inner_dict in item.items():
            if not isinstance(inner_dict, OrderedDict):
                inner_dict = OrderedDict(inner_dict)
            for inner_key, content in inner_dict.items():
                tag = mapping.get((outer_key, inner_key))
                if tag:
                    content = content.strip()
                    if tag == current_tag:
                        current_contents.append(content)
                    else:
                        if current_tag is not None:
                            xml_lines.append(f"<{current_tag}>")
                            xml_lines.append("\n\n".join(current_contents))
                            xml_lines.append(f"</{current_tag}>")
                            xml_lines.append("")  # blank line for readability
                        current_tag = tag
                        current_contents = [content]
                else:
                    # Ignore unmapped keys.
                    pass
    if current_tag is not None and current_contents:
        xml_lines.append(f"<{current_tag}>")
        xml_lines.append("\n\n".join(current_contents))
        xml_lines.append(f"</{current_tag}>")
        xml_lines.append("")

    return "\n".join(xml_lines)


def build_finetuning_example(cog_flow, question, system_message=None):
    """
    Build a finetuning example as a dictionary.
    - cog_flow: the model's chain-of-thought (a list of dictionaries).
    - question: the user prompt.
    - system_message: an optional system prompt.
    The assistant response is produced by converting the cog_flow into an XML string.
    """
    xml_thought = thought_flow_to_xml(cog_flow)
    example = {}
    if system_message:
        example["system"] = system_message
    example["user"] = question
    example["assistant"] = xml_thought
    return example


def convert_examples_to_markdown(examples, category_title):
    """
    Convert a list of finetuning examples into a Markdown string.
    Each example is a dict with keys: system (optional), user, assistant.
    """
    lines = [f"# {category_title}\n"]
    for idx, ex in enumerate(examples, start=1):
        lines.append(f"## Example {idx}")
        if "system" in ex:
            lines.append("### System Message")
            lines.append("")
            lines.append(ex["system"])
            lines.append("")
        lines.append("### User Prompt")
        lines.append("")
        lines.append(ex["user"])
        lines.append("")
        lines.append("### Assistant Response")
        lines.append("")
        lines.append("```")
        lines.append(ex["assistant"])
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def load_yaml(path):
    """Utility to load YAML from a file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading YAML from {path}: {e}")
        return None


def load_json(path):
    """Utility to load JSON from a file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON from {path}: {e}")
        return None


def main():
    # Folders for input:
    # Validator outputs (to check scores, question text, etc.)
    validator_folder = "../data_generation/validator_outputs"
    # Model responses (chain-of-thought data) from o7responses (assumed same filenames)
    model_folder = "../data_generation/o7responses"

    # Output files:
    jsonl_output_file = "finetuning_dataset.jsonl"
    md_output_folder = "finetuning_markdown"
    os.makedirs(md_output_folder, exist_ok=True)

    accepted_count = 0
    rejected_count = 0
    total_with_scores = 0
    min_score = None
    max_score = None
    rejected_examples = []

    # Open the global JSONL file for writing.
    jsonl_out = open(jsonl_output_file, 'w', encoding='utf-8')

    # Process each category (validator file)
    for filename in os.listdir(validator_folder):
        if not filename.lower().endswith('.json'):
            continue
        category = sanitize_category(filename)
        val_path = os.path.join(validator_folder, filename)
        model_path = os.path.join(model_folder, filename)  # Assume same filename.

        if not os.path.exists(model_path):
            print(f"Model response file not found for category '{category}'. Skipping.")
            continue

        validator_data = load_json(val_path)
        model_data = load_json(model_path)
        if validator_data is None or model_data is None:
            continue

        # Ensure the number of examples match.
        if len(validator_data) != len(model_data):
            print(
                f"Mismatch in examples for '{category}' (validator={len(validator_data)}, model={len(model_data)}). Skipping.")
            continue

        category_examples = []  # To accumulate finetuning examples for this category.

        for idx, (val_example, model_example) in enumerate(zip(validator_data, model_data), start=1):
            score = val_example.get("score")
            if score is None:
                continue
            try:
                score_int = int(score)
            except Exception as e:
                print(f"Error converting score '{score}' to int: {e}")
                continue
            total_with_scores += 1
            if min_score is None or score_int < min_score:
                min_score = score_int
            if max_score is None or score_int > max_score:
                max_score = score_int

            question = val_example.get("question", "").strip()
            if score_int < SCORE_THRESHOLD:
                rejected_count += 1
                rejected_examples.append({
                    "category": category,
                    "example_number": idx,
                    "question": question,
                    "score": score_int
                })
                continue

            # Build finetuning example using the model's chain-of-thought.
            example = build_finetuning_example(
                cog_flow=model_example,
                question=question,
                system_message=SYSTEM_PROMPT  # optional, can be omitted if desired.
            )
            # Write the example as a JSON line to the JSONL file.
            jsonl_out.write(json.dumps(example) + "\n")
            accepted_count += 1
            category_examples.append(example)

        # Create a Markdown file for this category.
        if category_examples:
            md_content = convert_examples_to_markdown(category_examples, category)
            md_filename = os.path.splitext(filename)[0] + ".md"
            md_file_path = os.path.join(md_output_folder, md_filename)
            try:
                with open(md_file_path, 'w', encoding='utf-8') as md_file:
                    md_file.write(md_content)
                print(f"Converted {filename} to Markdown: {md_file_path}")
            except Exception as e:
                print(f"Error writing Markdown to {md_file_path}: {e}")

    jsonl_out.close()
    print(f"\nCreated finetuning dataset with {accepted_count} examples in '{jsonl_output_file}'")
    print(f"Score threshold: {SCORE_THRESHOLD}")
    print(f"Rejected examples (score below threshold): {rejected_count}")
    if total_with_scores > 0:
        print(f"Minimum score encountered: {min_score}")
        print(f"Maximum score encountered: {max_score}")
    else:
        print("No examples with valid scores were found.")

    if rejected_examples:
        print("\nDetails of rejected examples:")
        for rej in rejected_examples:
            print(f"Category: {rej['category']}, Example #{rej['example_number']}, Score: {rej['score']}")


if __name__ == '__main__':
    main()
