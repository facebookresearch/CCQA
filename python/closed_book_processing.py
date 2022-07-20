# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import html
import json
import os
import re

from lxml import etree


def extract_text(input_text, keep_markup):
    input_text = input_text.replace("\n", "").replace("\r", "")
    if keep_markup:
        text = html.unescape(input_text)
    elif not keep_markup:
        text_root = etree.HTML(input_text)
        if text_root is None:
            return None
        text = " ".join(text_root.itertext())
        text = re.sub(" +", " ", text)
        text = text.encode("ascii", "xmlcharrefreplace").decode("utf-8")
        text = html.unescape(text)
    return text

def generate_closed_book_format(data_path, only_english, keep_markup, output_path):
    with open(data_path, "r") as f:
        question_list = []
        answer_list = []
        for website in f:
            content = json.loads(website)
            if only_english and content["Fasttext_language"] != "en":
                continue
            questions = content["Questions"]
            for question in questions:
                question_text = ""
                if "name_markup" in question.keys():
                    extracted_text = extract_text(question["name_markup"], keep_markup)
                    if extracted_text is not None:
                        question_text += extracted_text + " "
                if "text_markup" in question.keys():
                    extracted_text = extract_text(question["text_markup"], keep_markup)
                    if extracted_text is not None:
                        question_text += extracted_text
                if len(question_text) > 0:
                    for answer in question["Answers"]:
                        answer_text = None
                        if "text_markup" in answer.keys():
                            answer_text = extract_text(
                                answer["text_markup"], keep_markup
                            )
                        if (
                            answer_text is not None
                            and len(answer_text.replace("\n", "").replace("\r", "")) > 0
                        ):
                            question_list.append(question_text)
                            answer_list.append(answer_text)

    with open(output_path + ".source", "w") as f:
        for element in question_list:
            f.write(element.replace("\n", "").replace("\r", "") + "\n")
    with open(output_path + ".target", "w") as f:
        for element in answer_list:
            f.write(element.replace("\n", "").replace("\r", "") + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate sequence-to-sequence input and output for closed-book QA"
    )
    parser.add_argument("--data_path", help="Path to the json dataset")
    parser.add_argument("--output_path", help="Path to the output file")
    parser.add_argument(
        "--only_english",
        action="store_true",
        help="Only keep english samples in the dataset",
    )
    parser.add_argument(
        "--keep_markup", action="store_true", help="Keep the HTML markup"
    )
    args = parser.parse_args()
    generate_closed_book_format(
        args.data_path, args.only_english, args.keep_markup, args.output_path
    )
