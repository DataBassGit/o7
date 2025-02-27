import os
import time
import json
import yaml
from contextlib import contextmanager
from checkpoint_manager import CheckpointManager
from agentforge.cog import Cog

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
    def __init__(self, qas_file, output_dir='o7responses', max_retries=3, retry_delay=5):
        self.qas_file = qas_file
        self.output_dir = output_dir
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Initialize the Cog agent.
        self.o7 = Cog('o7')

        # Setup checkpoint management.
        self.checkpoint_manager = CheckpointManager("processed_categories.json")
        self.processed_categories = self.checkpoint_manager.load()

        # Timing data
        self.start_time = None
        self.timings = {}

    def start_time_counter(self):
        self.start_time = time.perf_counter()
        start_human = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"\nRun started at: {start_human}\n")

    def show_time_summary(self):
        total_elapsed = time.perf_counter() - self.start_time
        print(f"Total run time: {total_elapsed:.2f} seconds")
        print("Timing Summary:")
        for task, elapsed in self.timings.items():
            print(f" - {task}: {elapsed:.2f} seconds")

    def load_qa_data(self):
        """Load aggregated QA data from a YAML file."""
        try:
            print("Loading aggregated QAS YAML file...")
            with open(self.qas_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data
        except Exception as e:
            print(f"Error loading {self.qas_file}: {e}")
            return {}

    def process(self):
        """Main process: load QA data, process each category, and show timing summary."""
        self.start_time_counter()

        # Measure how long loading the main QA data takes
        with timer("load_qa_data", self.timings):
            qa_data = self.load_qa_data()

        if not qa_data:
            print("No QA data found to process.")
            self.show_time_summary()
            return

        total_categories = len(qa_data)

        # Time the processing for each category
        for idx, category in enumerate(sorted(qa_data.keys()), start=1):
            qa_list = qa_data.get(category, [])
            task_name = f"{category}_processing"
            with timer(task_name, self.timings):
                self.process_category(category, qa_list, idx, total_categories)

        self.show_time_summary()

    def process_category(self, category, qa_list, index, total):
        if category in self.processed_categories:
            print(f"Skipping already processed category: {category}")
            return

        safe_category = sanitize_category(category)
        output_file = os.path.join(self.output_dir, f"{safe_category}.json")
        if os.path.exists(output_file):
            os.remove(output_file)

        print(f"\nProcessing category ({index}/{total}): {category}")
        all_success = True
        for idx_q, qa in enumerate(qa_list, start=1):
            question = qa.get("question", "").strip()
            print(f"{'-' * 60}\nProcessing question {idx_q}:\n{question}\n")

            # (Optional) finer granularity timing for each question
            question_task_name = f"{category}_question_{idx_q}"
            with timer(question_task_name, self.timings):
                if not self.process_question(category, question):
                    print(f"Failed to process question {idx_q} after {self.max_retries} attempts.")
                    all_success = False
                    break

        if all_success:
            self.processed_categories.add(category)
            self.checkpoint_manager.save(self.processed_categories)
            print(f"Finished processing category: {category}")
        else:
            print(f"Category '{category}' encountered errors; it will be retried later.")

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
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = [data]
                    data.append(response)
                    f.seek(0)
                    json.dump(data, f, indent=2, sort_keys=True)
                    f.truncate()
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump([response], f, indent=2, sort_keys=True)
            print(f"Response appended to {file_path}")
        except Exception as e:
            print(f"Error writing response to file {file_path}: {e}")

if __name__ == '__main__':
    # Update to use the aggregated YAML file.
    qas_input_file = "../qa_gen/aggregated_qas.yaml"
    print("Initializing processing of QAs...")
    processor = ProcessQAsByCategory(qas_input_file)
    processor.process()

# import os
# import time
# import json
# import yaml
# from checkpoint_manager import CheckpointManager
# from agentforge.cog import Cog
#
#
# def sanitize_category(category):
#     """Convert category string into a filesystem-safe format."""
#     return category.replace(' ', '_').replace('/', '_')
#
#
# class ProcessQAsByCategory:
#     def __init__(self, qas_file, output_dir='o7responses', max_retries=3, retry_delay=5):
#         self.qas_file = qas_file
#         self.output_dir = output_dir
#         self.max_retries = max_retries
#         self.retry_delay = retry_delay
#
#         # Initialize the Cog agent.
#         self.o7 = Cog('o7')
#
#         # Setup checkpoint management.
#         self.checkpoint_manager = CheckpointManager("processed_categories.json")
#         self.processed_categories = self.checkpoint_manager.load()
#
#     def load_qa_data(self):
#         """Load aggregated QA data from a YAML file."""
#         try:
#             print("Loading aggregated QAS YAML file...")
#             with open(self.qas_file, "r", encoding="utf-8") as f:
#                 data = yaml.safe_load(f)
#             return data
#         except Exception as e:
#             print(f"Error loading {self.qas_file}: {e}")
#             return {}
#
#     def process_category(self, category, qa_list, index, total):
#         """Process all questions in a given category."""
#         if category in self.processed_categories:
#             print(f"Skipping already processed category: {category}")
#             return
#
#         safe_category = sanitize_category(category)
#         output_file = os.path.join(self.output_dir, f"{safe_category}.json")
#         # Remove any existing output for a fresh start.
#         if os.path.exists(output_file):
#             os.remove(output_file)
#
#         print(f"\nProcessing category ({index}/{total}): {category}")
#         all_success = True
#         for idx_q, qa in enumerate(qa_list, start=1):
#             question = qa.get("question", "").strip()
#             print(
#                 f"{'-' * 60}\nProcessing question {idx_q}:\n{question}\n"
#             )
#             if not self.process_question(category, question):
#                 print(f"Failed to process question {idx_q} after {self.max_retries} attempts.")
#                 all_success = False
#                 break
#
#         if all_success:
#             self.processed_categories.add(category)
#             self.checkpoint_manager.save(self.processed_categories)
#             print(f"Finished processing category: {category}")
#         else:
#             print(f"Category '{category}' encountered errors; it will be retried later.")
#
#     def process_question(self, category, question):
#         """Attempt to process a question with retry logic."""
#         attempts = 0
#         while attempts < self.max_retries:
#             try:
#                 self.o7.run(question=question)
#                 flow_trail = self.o7.get_track_flow_trail()
#
#                 self.write_response(category, flow_trail)
#                 return True
#             except Exception as e:
#                 attempts += 1
#                 print(f"Error processing question (attempt {attempts}/{self.max_retries}): {e}")
#                 time.sleep(self.retry_delay)
#         return False
#
#     def write_response(self, category, response):
#         """Append the response to the output file for the given category in JSON format."""
#         os.makedirs(self.output_dir, exist_ok=True)
#         safe_category = sanitize_category(category)
#         file_path = os.path.join(self.output_dir, f"{safe_category}.json")
#         try:
#             if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
#                 with open(file_path, 'r+', encoding='utf-8') as f:
#                     data = json.load(f)
#                     if not isinstance(data, list):
#                         data = [data]
#                     data.append(response)
#                     f.seek(0)
#                     json.dump(data, f, indent=2, sort_keys=True)
#                     f.truncate()
#             else:
#                 with open(file_path, 'w', encoding='utf-8') as f:
#                     json.dump([response], f, indent=2, sort_keys=True)
#             print(f"Response appended to {file_path}")
#         except Exception as e:
#             print(f"Error writing response to file {file_path}: {e}")
#
#     def process(self):
#         """Main process: load QA data and process each category."""
#         qa_data = self.load_qa_data()
#         if not qa_data:
#             print("No QA data found to process.")
#             return
#
#         total_categories = len(qa_data)
#         for idx, category in enumerate(sorted(qa_data.keys()), start=1):
#             qa_list = qa_data.get(category, [])
#             self.process_category(category, qa_list, idx, total_categories)
#
#
# if __name__ == '__main__':
#     # Update to use the aggregated YAML file.
#     qas_input_file = "../qa_gen/aggregated_qas.yaml"
#     print("Initializing processing of QAs...")
#     processor = ProcessQAsByCategory(qas_input_file)
#     processor.process()
