import os
import json


def get_json_files(directory):
    """
    Retrieve a list of JSON file paths from the given directory.
    """
    json_files = []
    for file_name in os.listdir(directory):
        if file_name.lower().endswith('.json'):
            json_files.append(os.path.join(directory, file_name))
    return json_files


def sanitize_category(file_name):
    """
    Convert a file name into a safe category string (without extension).
    """
    category = os.path.splitext(file_name)[0]
    return category.replace(' ', '_').replace('/', '_')


def load_json_file(file_path):
    """
    Load and return the data from a JSON file.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def aggregate_category_data(directory):
    """
    Aggregate JSON data from all files in the given directory.
    Returns a dictionary mapping sanitized category names to the file's data.
    """
    aggregated_data = {}
    json_files = get_json_files(directory)
    for file_path in json_files:
        file_name = os.path.basename(file_path)
        category = sanitize_category(file_name)
        try:
            data = load_json_file(file_path)
            aggregated_data[category] = data
        except Exception as e:
            print(f"Error processing {file_name}: {e}")
    return aggregated_data


def save_aggregated_data(aggregated_data, output_file):
    """
    Save the aggregated JSON data to a file.
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(aggregated_data, f, indent=2, sort_keys=True)
    print(f"Aggregated data saved to {output_file}")


def main():
    responses_folder = 'o7responses'
    output_file = 'aggregated_responses.json'

    if not os.path.exists(responses_folder):
        print(f"Folder '{responses_folder}' does not exist.")
        return

    aggregated_data = aggregate_category_data(responses_folder)
    if aggregated_data:
        save_aggregated_data(aggregated_data, output_file)
    else:
        print("No data found to aggregate.")


if __name__ == '__main__':
    main()
