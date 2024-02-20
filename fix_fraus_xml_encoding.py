import argparse

def fix_encoding(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f_in, open(output_file, 'w', encoding='utf-8') as f_out:
        for line in f_in:
            if line.startswith('<?xml version="1.0" encoding="utf-16"?>'):
                line = line.replace("utf-16", "utf-8")
            f_out.write(line)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fix encoding in FRAUS XML files')
    parser.add_argument('input_file', help='Path to the input XML file')
    parser.add_argument('output_file', help='Path to the output XML file')
    args = parser.parse_args()

    fix_encoding(args.input_file, args.output_file)
