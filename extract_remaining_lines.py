#!/usr/bin/env python3
"""
Script: extract_remaining_lines.py
Description:
  This script accepts three command line parameters:
    1. full_list: A text file containing a full list of lines.
    2. partial_list: A text file containing a partial list.
    3. remaining_list: The output file where the program writes lines that are in full_list
       (after sorting and removing duplicate lines) but not in partial_list (after the same processing).

Usage:
  $ python extract_remaining_lines.py <full_list> <partial_list> <remaining_list>
  
If fewer than three parameters are provided, the script will print an intelligent error message and exit.
"""

import sys
import os

def read_sort_and_deduplicate(file_path):
    """
    Reads the lines from the given file (assumed UTF-8 encoded),
    sorts them in alphanumeric order (similar to Linux 'sort'),
    and removes duplicates (keeping only the first occurrence from a sorted list).

    Returns:
        List of unique sorted lines.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # Read and remove newlines
            lines = [line.rstrip("\n") for line in f.readlines()]
    except Exception as e:
        print(f"ERROR: Cannot read file '{file_path}'. Exception: {e}")
        sys.exit(1)
    
    # Sort lines in alphanumeric order
    sorted_lines = sorted(lines)
    
    # Remove duplicate consecutive lines (after sort, duplicates are adjacent)
    unique_lines = []
    previous_line = None
    for line in sorted_lines:
        if line != previous_line:
            unique_lines.append(line)
            previous_line = line
    return unique_lines

def main():
    # Check for the required three command-line parameters.
    if len(sys.argv) < 4:
        print("ERROR: Insufficient parameters provided.")
        print("Usage: extract_remaining_lines.py <full_list> <partial_list> <remaining_list>")
        sys.exit(1)
    
    full_list_path = sys.argv[1]
    partial_list_path = sys.argv[2]
    remaining_list_path = sys.argv[3]
    
    # Validate that full_list and partial_list exist and are files.
    if not os.path.isfile(full_list_path):
        print(f"ERROR: The file '{full_list_path}' does not exist or is not a valid file.")
        sys.exit(1)
    if not os.path.isfile(partial_list_path):
        print(f"ERROR: The file '{partial_list_path}' does not exist or is not a valid file.")
        sys.exit(1)
    
    print("INFO: Both input files exist. Beginning to process files...")
    
    # Process the full_list file.
    full_unique_lines = read_sort_and_deduplicate(full_list_path)
    print(f"INFO: Processed '{full_list_path}' with {len(full_unique_lines)} unique sorted lines.")
    
    # Process the partial_list file.
    partial_unique_lines = read_sort_and_deduplicate(partial_list_path)
    print(f"INFO: Processed '{partial_list_path}' with {len(partial_unique_lines)} unique sorted lines.")
    
    # Compute the difference: lines in full_unique_lines but not in partial_unique_lines.
    partial_set = set(partial_unique_lines)
    remaining_lines = [line for line in full_unique_lines if line not in partial_set]
    print(f"INFO: Found {len(remaining_lines)} lines in '{full_list_path}' that are not in '{partial_list_path}'.")
    
    # Write the remaining lines to the output file.
    try:
        with open(remaining_list_path, "w", encoding="utf-8") as outfile:
            for line in remaining_lines:
                outfile.write(line + "\n")
        print(f"SUCCESS: Remaining lines have been successfully written to '{remaining_list_path}'.")
    except Exception as e:
        print(f"ERROR: Failed to write to '{remaining_list_path}'. Exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
