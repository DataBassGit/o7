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
                 output_dir='qas', num_questions=4):
        self.categories_file = categories_file
        self.checkpoint_file = checkpoint_file
        self.output_dir = output_dir
        self.num_questions = num_questions

        self._parser = ParsingProcessor()
        self.checkpoint_manager = CheckpointManager(checkpoint_file)
        self.processed_categories = self.checkpoint_manager.load()
        self.agent = Agent('QAGenAgent')
        self.categories = self.load_categories()
        self.start_time = None
        self.timings = {}  # Dictionary to store timing information

    def load_categories(self):
        with open(self.categories_file, 'r') as file:
            return [line.strip() for line in file if line.strip()]

    @staticmethod
    def sanitize_category(category):
        return category.replace(' ', '_').replace('/', '_')

    def generate_qa_pairs_for_category(self, category):
        qa_pairs = []
        previous_questions = []
        for idx in range(self.num_questions):
            task_name = f"question_{idx+1}_generation"
            with timer(task_name, self.timings):
                prev_qs = "\n".join(previous_questions)
                result = self.agent.run(topic=category, previous_questions=prev_qs.strip())
                qa_pair = self._parser.parse_by_format(result, 'yaml', ['~~~', '```'])
                qa_pairs.append(qa_pair)
                # Format the question slightly to help ensure uniqueness.
                new_question = f'- {qa_pair.get("question", "").strip()}\n'
                previous_questions.append(new_question)
        return qa_pairs

    def save_qa_pairs(self, category, qa_pairs):
        os.makedirs(self.output_dir, exist_ok=True)
        sanitized = self.sanitize_category(category)
        output_file = os.path.join(self.output_dir, f"{sanitized}.yaml")
        with open(output_file, 'w') as f:
            yaml.dump(qa_pairs, f, sort_keys=False)
        return output_file

    # def update_checkpoint(self, category):
    #     self.processed_categories.add(category)
    #     self.checkpoint_manager.save(self.processed_categories)

    def update_checkpoint(self, category):
        self.processed_categories.add(category)
        # Retrieve the processing time for the category from self.timings.
        cat_time = self.timings.get(f"{category}_processing", 0)
        # Save both the processed set and the timing information.
        self.checkpoint_manager.save(self.processed_categories, timings={category: cat_time})


    def process_category(self, category):
        with timer(f"{category}_processing", self.timings):
            print(f"Generating QA pairs for category: {category}")
            qa_pairs = self.generate_qa_pairs_for_category(category)
            output_file = self.save_qa_pairs(category, qa_pairs)
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