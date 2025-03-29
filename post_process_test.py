#!/usr/bin/env python3
import sys
import os
import yaml


def post_process_yaml_file(file_path):
    """
    Post-process the YAML file to ensure proper formatting:
    - All string values use block scalar format with pipe symbol
    - Properly preserved newlines
    - No quotes around strings that should be block scalar literals
    - Convert escaped newlines to actual newlines with proper indentation
    
    Returns:
        list: Formatting issues found, empty list if no issues
    """
    with open(file_path, 'r') as f:
        content = f.read()

    # Track formatting issues found
    formatting_issues = []

    import re

    # Pattern to detect YAML entries with issues
    # Match patterns like:
    # - "key": "value" or 'key': 'value' (quoted key and quoted value)
    # - key: "value" or key: 'value' (unquoted key and quoted value)
    PATTERN_TO_MATCH = r'(\s*-?\s*(?:"[^"]+"|\'[^\']+\'|\w+):\s*)(["\'])(.*?)(\2)'

    yaml_key_value_pattern = re.compile(PATTERN_TO_MATCH, re.DOTALL)

    # Check for quoted strings that should use block scalar format
    matches = yaml_key_value_pattern.findall(content)
    if matches:
        issue_description = "Quoted strings that should use block scalar format"
        formatting_issues.append(issue_description)
        print(f"  Found issue: {issue_description} in: {file_path}")
        for match in matches[:2]:  # Show up to 2 examples
            preview = match[2][:50] + "..." if len(match[2]) > 50 else match[2]
            print(f"    Example: {match[0]}{match[1]}{preview}{match[3]}")

    # Check for multi-line quoted strings that should use pipe notation
    # Pattern to also match both quoted and unquoted keys
    multiline_quoted = re.compile(PATTERN_TO_MATCH, re.DOTALL)
    multiline_matches = [m for m in multiline_quoted.findall(content) if '\n' in m[2] or '\\n' in m[2]]
    if multiline_matches:
        issue_description = "Multi-line quoted strings that should use pipe notation"
        if issue_description not in formatting_issues:
            formatting_issues.append(issue_description)
        print(f"  Found issue: {issue_description} in: {file_path}")
        for match in multiline_matches[:2]:  # Show up to 2 examples
            preview = match[2][:50] + "..." if len(match[2]) > 50 else match[2]
            print(f"    Example: {match[0]}{match[1]}{preview}{match[3]}")

    # Check for strings with escaped newlines
    escaped_newline_matches = [m for m in yaml_key_value_pattern.findall(content) if '\\n' in m[2]]
    if escaped_newline_matches:
        issue_description = "Strings with escaped newlines that need to be converted"
        if issue_description not in formatting_issues:
            formatting_issues.append(issue_description)
        print(f"  Found issue: {issue_description} in: {file_path}")
        for match in escaped_newline_matches[:2]:  # Show up to 2 examples
            preview = match[2][:50] + "..." if len(match[2]) > 50 else match[2]
            print(f"    Example: {match[0]}{match[1]}{preview}{match[3]}")

    # If there are no formatting issues, return early
    if not formatting_issues:
        print(f"  No formatting issues found in: {file_path}")
        return formatting_issues

    print(f"  Post-processing YAML file to fix {len(formatting_issues)} type(s) of formatting issues: {file_path}")
    print(f"  Issues to fix: {', '.join(formatting_issues)}")

    # Manually fix the YAML content
    fixed_content = content
    for match in yaml_key_value_pattern.findall(content):
        key_part = match[0]
        quote_type = match[1]
        value = match[2].strip()
        
        # Create the replacement with block scalar format using pipe
        # Only replace if the value isn't already in block scalar format
        original = f"{key_part}{quote_type}{value}{quote_type}"
        
        # Check if there are actual newlines or escaped newlines
        has_actual_newlines = '\n' in value
        has_escaped_newlines = '\\n' in value
        
        if has_actual_newlines or has_escaped_newlines:
            # For multiline strings, use the pipe notation
            replacement = f"{key_part}|-\n"
            
            # Calculate indentation level based on key position
            # Find position where the key starts in the line
            key_position = len(key_part) - len(key_part.lstrip())
            # Add exactly 2 spaces from the key position
            indent = " " * (key_position + 1)
            
            # Process the value:
            # 1. Replace escaped newlines with actual newlines
            if has_escaped_newlines:
                # First unescape any escaped newlines and other escape sequences
                import codecs
                value = codecs.decode(value, 'unicode_escape')
            
            # 2. Split by actual newlines and indent each line
            lines = value.split('\n')
            # Clean any leading/trailing whitespace from each line
            lines = [line.strip() for line in lines]
            # Add consistent indentation to each non-empty line
            indented_lines = []
            for line in lines:
                if line.strip():  # Only apply indentation to non-empty lines
                    indented_lines.append(f"{indent}{line}")
                else:
                    indented_lines.append("")  # Keep empty lines
                    
            indented_value = '\n'.join(indented_lines)
            
            replacement += indented_value
        else:
            # For single line strings, just remove quotes
            replacement = f"{key_part}{value}"
            
        fixed_content = fixed_content.replace(original, replacement)

    # Create new file path with "_fixed" suffix 
    fixed_file_path = file_path.replace(".yaml", "_fixed.yaml")

    # Write the fixed content directly
    with open(fixed_file_path, 'w') as f:
        f.write(fixed_content)
                  
    return formatting_issues


def post_process_test(yaml_file):
    # Call post_process_yaml_file and store issues found
    issues = post_process_yaml_file(yaml_file)
    
    # Only show before/after content if issues were found
    if not issues:
        print(f"No issues found in: {yaml_file}")
        return
    
    # Print the first few lines of the file before processing
    print("\n=== Before Post-Processing ===")
    with open(yaml_file, 'r') as f:
        content = f.read()
        print(content[:500] + "...\n" if len(content) > 500 else content)
    
    # Print the first few lines after processing (fixed file)
    fixed_file_path = yaml_file.replace(".yaml", "_fixed.yaml")
    if os.path.exists(fixed_file_path):
        print("\n=== After Post-Processing ===")
        with open(fixed_file_path, 'r') as f:
            content = f.read()
            print(content[:500] + "...\n" if len(content) > 500 else content)

if __name__ == "__main__":
    # Use the first argument as the YAML file path, or a default if not provided
    # yaml_file = sys.argv[1] if len(sys.argv) > 1 else "data_generation/qas/astro-ph.CO_Cosmology_and_Nongalactic_Astrophysics.yaml"
    
    # find file from current directory
    y_file = os.path.join(os.path.dirname(__file__), "test_format.yaml")

    if not os.path.exists(y_file):
        print(f"Error! File not found: {y_file}")
        sys.exit(1)
    
    print(f"Testing post-processing on file: {y_file}")
    post_process_test(y_file)