import xml.etree.ElementTree as ET
from html import unescape
import argparse

def parse_and_unescape_xml(input_file, output_file, skip_xml_declaration):
    with open(input_file, 'r', encoding='utf-8') as f:
        if skip_xml_declaration:
            # skip the first line (<?xml version="1.0" encoding="utf-16"?>)
            # fixes parse error for the FRAUS XML because it is actually utf-8
            f.readline()
        # Parse the XML file
        tree = ET.parse(f)
    root = tree.getroot()

    # Iterate through ExText tags and unescape their content
    for ex_text in root.iter('ExText'):
        if ex_text.text is not None:
            ex_text.text = unescape(ex_text.text)

    # Write the modified XML to a new file
    tree.write(output_file, encoding='utf-8', xml_declaration=True)

# The following function produces ill-formed XML for FRAUS samples
# def unescape_lines(input_file, output_file):
#     with open(input_file, 'r', encoding='utf-8') as f_in, open(output_file, 'w', encoding='utf-8') as f_out:
#         for line in f_in:
#             if line.startswith('<?xml version="1.0" encoding="utf-16"?>'):
#                 line = line.replace("utf-16", "utf-8")
#             line = unescape(line)
#             line = unescape(line)
#             f_out.write(line)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Parse XML file and unescape ExText tags')
    parser.add_argument('input_file', help='Path to the input XML file')
    parser.add_argument('output_file', help='Path to the output XML file')
    parser.add_argument('--skip-xml-declaration', action=argparse.BooleanOptionalAction, help='Skip the XML declaration')
    args = parser.parse_args()

    parse_and_unescape_xml(args.input_file, args.output_file, args.skip_xml_declaration)
    # unescape_lines(args.input_file, args.output_file)
