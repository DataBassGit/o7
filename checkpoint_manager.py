import os
import json


class CheckpointManager:
    def __init__(self, filename):
        """
        Initialize the checkpoint manager. The checkpoint file will be stored in a 'checkpoints'
        folder.
        """
        self.folder = "checkpoints"
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
        self.filepath = os.path.join(self.folder, filename)
        # Structure of the checkpoint data:
        # {
        #    "processed": [list of category names],
        #    "times": { "category_name": processing_time, ... }
        # }
        self.data = {
            "processed": [],
            "times": {}
        }
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"Error loading checkpoint file: {e}")

    def load(self):
        """Return the set of processed categories."""
        return set(self.data.get("processed", []))

    def save(self, processed_set, timings=None):
        """
        Save the processed categories and optionally update the processing times.

        :param processed_set: a set (or list) of processed category names.
        :param timings: a dictionary mapping category names to their processing times.
        """
        self.data["processed"] = list(processed_set)
        if timings:
            self.data["times"].update_memory(timings)
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving checkpoint file: {e}")
