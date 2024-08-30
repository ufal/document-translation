import argparse
from html import unescape, escape

def transform_lines(input_file, output_file, fun):
    with open(input_file, 'r', encoding='utf-8') as f_in, open(output_file, 'w', encoding='utf-8') as f_out:
        for line in f_in:
            line = fun(line)
            f_out.write(line)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Parse XML file and unescape ExText tags')
    parser.add_argument('input_file', help='Path to the input XML file')
    parser.add_argument('output_file', help='Path to the output XML file')
    parser.add_argument('--escape', action=argparse.BooleanOptionalAction, help='Escape the lines')
    parser.add_argument('--unescape', action=argparse.BooleanOptionalAction, help='Escape the lines')
    parser.add_argument('--twice', action=argparse.BooleanOptionalAction, help='Apply the transformation twice')
    args = parser.parse_args()

    assert bool(args.escape) ^ bool(args.unescape), "Exactly one of --escape and --unescape must be set"

    if args.twice:
        my_unescape = lambda x: unescape(unescape(x))
        my_escape = lambda x: escape(escape(x))
    else:
        my_unescape = unescape
        my_escape = escape

    if args.unescape:
        transform_lines(args.input_file, args.output_file, my_unescape)
    else:
        transform_lines(args.input_file, args.output_file, my_escape)
