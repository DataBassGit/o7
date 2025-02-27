import os
import yaml

def get_yaml_files(directory):
    """
    Retrieve a list of YAML file paths from the given directory.
    """
    yaml_files = []
    for file_name in os.listdir(directory):
        if file_name.lower().endswith(('.yaml', '.yml')):
            yaml_files.append(os.path.join(directory, file_name))
    return yaml_files

def load_yaml_file(file_path):
    """
    Load and return the data from a YAML file.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def sanitize_category(file_name):
    """
    Convert a file name into a sanitized category name.
    """
    category = os.path.splitext(file_name)[0]
    return category.replace(' ', '_').replace('/', '_')

def aggregate_qa_data(qas_folder):
    """
    Aggregate QA pairs from each YAML file in the specified folder.
    Returns a dictionary mapping category names to lists of QA pairs.
    """
    aggregated_data = {}
    yaml_files = get_yaml_files(qas_folder)
    for file_path in yaml_files:
        file_name = os.path.basename(file_path)
        category = sanitize_category(file_name)
        try:
            data = load_yaml_file(file_path)
            if data:
                aggregated_data[category] = data
            else:
                print(f"No data found in {file_name}.")
        except Exception as e:
            print(f"Error processing {file_name}: {e}")
    return aggregated_data

def save_aggregated_data(aggregated_data, output_file):
    """
    Save the aggregated QA data to a YAML file.
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(aggregated_data, f, sort_keys=True)
    print(f"Aggregated QA data saved to {output_file}")

def main():
    qas_folder = 'qas'
    output_file = 'aggregated_qas.yaml'
    if not os.path.exists(qas_folder):
        print(f"Folder '{qas_folder}' does not exist.")
        return

    aggregated_data = aggregate_qa_data(qas_folder)
    if not aggregated_data:
        print("No QA data found to aggregate.")
        return

    save_aggregated_data(aggregated_data, output_file)

if __name__ == '__main__':
    main()
