# o7

o7 is an advanced problem-solving agent designed for researchers who want to generate, process, and validate custom Q&A fine-tuning datasets. Built on the [AgentForge](https://github.com/DataBassGit/AgentForge) framework, o7 uses a cognitive chain-of-thought approach to produce well-reasoned, step-by-step analysis. It was originally inspired by the Dignity project, but retains only the essential cognitive loop—removing Discord or other overhead—to keep things streamlined.

## Key Features

o7 supports chain-of-thought reasoning to tackle complex queries, script-based Q&A generation, and flexible configuration through **AgentForge**’s prompts and multi-agent architecture. You can easily generate datasets from a list of topics, process them with o7’s cognitive loop, validate the model’s answers, and even create a fine-tuning dataset from validated responses.

## Architecture and Inspiration

The system borrows the essential architecture from Dignity (formerly Trinity), which relies on multiple agents (e.g., **thought**, **theory**, **cot**, **reflect**, and **generate**) working in concert to produce robust reasoning. o7 removes the Discord-specific integrations found in Dignity, focusing squarely on Q&A dataset generation. You can still customize each sub-agent in `custom_agents/o7Agent.py` and update the prompts in `.agentforge/prompts` to shape the tone, style, or logic of o7.

## Installation and Configuration

After cloning or downloading the repository, make sure you have [**AgentForge**](https://github.com/DataBassGit/AgentForge) installed:

```bash
pip install agentforge
```

If you’re integrating with external LLM providers (e.g., Anthropic or HuggingFace), set environment variables (like `ANTHROPIC_API_KEY`) according to [**AgentForge**’s documentation](https://github.com/DataBassGit/AgentForge). This ensures o7 has what it needs to interact with your chosen models.

## Usage Overview

At a high level, you’ll provide a list of categories or topics (`categories.txt`), then generate Q&A pairs for each category. After that, you can aggregate all those Q&As, feed them to o7 for chain-of-thought reasoning, and finally validate o7’s answers. The main scripts to know about are:

- **`qa_generation.py`** in `qa_gen/` reads each topic from `categories.txt` and creates initial Q&A pairs in Markdown files in `qa_gen/qas`.
- **`aggregate_qas.py`** then combines those Markdown Q&A files into a single JSON (`qa_gen/qas.json`) for easier processing.
- **`process_qas_by_category.py`** reads that JSON, feeds each question to o7, and records the chain-of-thought reasoning and final answer in JSON files under `process_qas/o7responses`.
- **`aggregate_o7responses.py`** (in `process_qas/`) takes all per-category JSON files in `process_qas/o7responses` and merges them into one file, `o7responses.json`.  
- **`convert_o7responses_to_md.py`** (also in `process_qas/`) creates Markdown files from each category’s JSON, making it simple to read or share o7’s answers.
  
This sequence starts with generating raw Q&A, continues with answering them via o7, and finally aggregates everything for quick navigation. A typical pipeline might look like this:

```bash
# Step 1: Generate QA pairs from categories.
python qa_gen/qa_generation.py

# Step 2: Aggregate those QAs into a single JSON.
python qa_gen/aggregate_qas.py

# Step 3: Process them with o7’s cognitive loop.
python process_qas/process_qas_by_category.py

# (Optional) Merge individual response files into one JSON.
python process_qas/aggregate_o7responses.py

# (Optional) Convert that merged JSON to Markdown files.
python process_qas/convert_o7responses_to_md.py
```

## Validation and Fine-Tuning

In addition to generating and processing Q&A data, o7 can validate its own answers against known “gold” answers and even help you create a fine-tuning dataset.

### Validator Scripts

You’ll find the validator logic in the `validator/` folder, though there are a few key steps:

1. **`run_validator.py`** looks at the “gold” Q&A in `qa_gen/qas.json`, compares them to the corresponding answers in `process_qas/o7responses.json`, and calls a Validator Agent to produce an assessment and score for each response. Results are saved as per-category JSON files in `validator_outputs`.
2. **`aggregate_validator_outputs.py`** merges all those per-category validator outputs into a single JSON file (`validator_outputs.json`).
3. **`convert_validator_to_md.py`** creates Markdown summaries of the validator outputs, which is handy if you want a quick glance at how well o7 performed and why.

### Creating a Fine-Tuning Dataset

Once you’ve validated o7’s answers, you can generate a JSONL file for fine-tuning language models by running **`create_finetuning_dataset.py`**. This script reads each validator output, filters out low-scoring responses, and writes the remaining high-quality Q&A pairs to a JSONL file (`finetuning_dataset.jsonl`). You can then use this dataset to fine-tune your model.  
   
Here’s a brief idea of how the validation workflow might look:

```bash
# Step 1: Validate O7’s responses with a Validator Agent.
python validator/run_validator.py

# Step 2: Aggregate all validation results into one JSON.
python validator/aggregate_validator_outputs.py

# Step 3: (Optional) Convert those validation results to Markdown.
python validator/convert_validator_to_md.py

# Step 4: Create a fine-tuning dataset from the validator outputs.
python validator/create_finetuning_dataset.py
```

The scripts let you see how o7’s answers compare to ground truth, adjust your chain-of-thought reasoning prompts accordingly, and build a refined dataset for training or fine-tuning external models.

## Example: Generating and Validating a Dataset

A typical end-to-end workflow might look like this:  
1. Edit `categories.txt` and add any new topics or questions you’d like to explore.  
2. Run `qa_generation.py` to produce initial Markdown files in `qa_gen/qas`.  
3. Run `aggregate_qas.py` to combine those files into `qa_gen/qas.json`.  
4. Process the entire set via `process_qas_by_category.py`, which calls o7’s chain-of-thought logic and writes answers to `process_qas/o7responses/<category>.json`.  
5. (Optional) Merge individual category responses into `o7responses.json` using `aggregate_o7responses.py` and convert them to Markdown with `convert_o7responses_to_md.py`.  
6. Validate everything with `run_validator.py`, which produces `validator_outputs/<category>.json`.  
7. Aggregate validation results into a single file using `aggregate_validator_outputs.py`, then optionally generate Markdown summaries with `convert_validator_to_md.py`.  
8. Finally, run `create_finetuning_dataset.py` to build a JSONL file that filters out low-quality answers and keeps only responses above a configurable score threshold.

## Contributions and Feedback

We welcome any thoughts on improving o7’s reasoning capabilities, expanding the validation features, or making the Q&A generation more powerful. If you have bug reports, enhancement ideas, or code contributions, feel free to open an issue or pull request on [GitHub](https://github.com/DataBassGit/AgentForge). You can also reach out directly if you have any questions or need guidance.

We hope o7 provides a streamlined, flexible system for generating and refining Q&A datasets with step-by-step reasoning. Happy exploring—and hacking on—this cognitive agent!

---

**References**  
[1] [AgentForge on GitHub](https://github.com/DataBassGit/AgentForge)  
[2] [Chain-of-Thought Paper](https://arxiv.org/abs/2201.11903)  
[3] [Reflexion Paper](https://arxiv.org/abs/2303.11366)
