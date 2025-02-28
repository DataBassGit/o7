import os
import time
import json
import yaml
from contextlib import contextmanager
from checkpoint_manager import CheckpointManager
from agentforge.cog import Cog
from collections import OrderedDict

@contextmanager
def timer(task_name, timings):
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    timings[task_name] = elapsed

def sanitize_category(category):
    """Convert category string into a filesystem-safe format."""
    return category.replace(' ', '_').replace('/', '_')

class ProcessQAsByCategory:
    def __init__(self, qas_folder, output_dir='o7responses', max_retries=3, retry_delay=5):
        """
        :param qas_folder: Folder containing one YAML file per category of QA data.
        """
        self.qas_folder = qas_folder
        self.output_dir = output_dir
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Initialize the Cog agent.
        self.o7 = Cog('o7')

        # Setup checkpoint management.
        # Using a checkpoint file that will be saved in the checkpoints folder.
        self.checkpoint_manager = CheckpointManager("processed_categories.json")
        self.processed_categories = self.checkpoint_manager.load()

        # Timing data.
        self.start_time = None
        self.timings = {}

    def start_time_counter(self):
        self.start_time = time.perf_counter()
        start_human = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"\nRun started at: {start_human}\n")

    def show_time_summary(self):
        total_elapsed = time.perf_counter() - self.start_time
        print(f"\nTotal run time: {total_elapsed:.2f} seconds")
        print("Timing Summary:")
        for task, elapsed in self.timings.items():
            print(f" - {task}: {elapsed:.2f} seconds")

    def load_all_qa_data(self):
        """
        Load all QA data from YAML files in the qas_folder.
        Returns a dictionary mapping category names to their QA list.
        """
        data = {}
        if not os.path.exists(self.qas_folder):
            print(f"QAs folder '{self.qas_folder}' does not exist.")
            return data
        for filename in os.listdir(self.qas_folder):
            if filename.endswith(".yaml"):
                category = os.path.splitext(filename)[0]
                path = os.path.join(self.qas_folder, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        qa_data = yaml.safe_load(f)
                    data[category] = qa_data
                except Exception as e:
                    print(f"Error loading {path}: {e}")
        return data

    def process(self):
        """Main process: load QA data from all files, process each category, and show timing summary."""
        self.start_time_counter()

        with timer("load_all_qa_data", self.timings):
            qa_data = self.load_all_qa_data()

        if not qa_data:
            print("No QA data found to process.")
            self.show_time_summary()
            return

        total_categories = len(qa_data)
        # Process each category file.
        for idx, category in enumerate(sorted(qa_data.keys()), start=1):
            if category in self.processed_categories:
                print(f"Skipping already processed category: {category}")
                continue
            qa_list = qa_data.get(category, [])
            task_name = f"{category}_processing"
            with timer(task_name, self.timings):
                self.process_category(category, qa_list, idx, total_categories)
            # Record processing time for this category.
            cat_time = self.timings.get(task_name, 0)
            self.processed_categories.add(category)
            self.checkpoint_manager.save(self.processed_categories, timings={category: cat_time})
            print(f"Finished processing category: {category}")
        self.show_time_summary()

    def process_category(self, category, qa_list, index, total):
        safe_category = sanitize_category(category)
        output_file = os.path.join(self.output_dir, f"{safe_category}.json")
        if os.path.exists(output_file):
            os.remove(output_file)

        print(f"\nProcessing category ({index}/{total}): {category}")
        all_success = True
        for idx_q, qa in enumerate(qa_list, start=1):
            question = qa.get("question", "").strip()
            print(f"{'-'*60}\nProcessing question {idx_q}:\n{question}\n")

            # Optional finer granularity timing for each question.
            question_task_name = f"{category}_question_{idx_q}"
            with timer(question_task_name, self.timings):
                if not self.process_question(category, question):
                    print(f"Failed to process question {idx_q} after {self.max_retries} attempts.")
                    all_success = False
                    break

        if not all_success:
            print(f"Category '{category}' encountered errors; it will be retried later.")
        else:
            print(f"Responses for category '{category}' saved to file: {output_file}")

    def process_question(self, category, question):
        """Attempt to process a question with retry logic."""
        attempts = 0
        while attempts < self.max_retries:
            try:
                self.o7.run(question=question)
                flow_trail = self.o7.get_track_flow_trail()
                self.write_response(category, flow_trail)
                return True
            except Exception as e:
                attempts += 1
                print(f"Error processing question (attempt {attempts}/{self.max_retries}): {e}")
                time.sleep(self.retry_delay)
        return False

    def write_response(self, category, response):
        """Append the response to the output file for the given category in JSON format."""
        os.makedirs(self.output_dir, exist_ok=True)
        safe_category = sanitize_category(category)
        file_path = os.path.join(self.output_dir, f"{safe_category}.json")
        try:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                with open(file_path, 'r+', encoding='utf-8') as f:
                    data = json.load(f, object_pairs_hook=OrderedDict)
                    if not isinstance(data, list):
                        data = [data]
                    data.append(response)
                    f.seek(0)
                    json.dump(data, f, indent=2, sort_keys=False)
                    f.truncate()
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump([response], f, indent=2, sort_keys=False)
            print(f"Response appended to {file_path}")
        except Exception as e:
            print(f"Error writing response to file {file_path}: {e}")

    # def write_response(self, category, response):
    #     """Append the response to the output file for the given category in JSON format."""
    #     os.makedirs(self.output_dir, exist_ok=True)
    #     safe_category = sanitize_category(category)
    #     file_path = os.path.join(self.output_dir, f"{safe_category}.json")
    #     try:
    #         if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
    #             with open(file_path, 'r+', encoding='utf-8') as f:
    #                 data = json.load(f)
    #                 if not isinstance(data, list):
    #                     data = [data]
    #                 data.append(response)
    #                 f.seek(0)
    #                 json.dump(data, f, indent=2, sort_keys=True)
    #                 f.truncate()
    #         else:
    #             with open(file_path, 'w', encoding='utf-8') as f:
    #                 json.dump([response], f, indent=2, sort_keys=True)
    #         print(f"Response appended to {file_path}")
    #     except Exception as e:
    #         print(f"Error writing response to file {file_path}: {e}")

if __name__ == '__main__':
    # Now we pass a folder path instead of an aggregated file.
    qas_folder = "qas"  # Folder containing one YAML file per category.
    print("Initializing processing of QAs...")
    processor = ProcessQAsByCategory(qas_folder)
    processor.process()
