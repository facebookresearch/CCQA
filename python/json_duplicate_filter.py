# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import copy
import html
import json
import re
import string

from lxml import etree


def extract_text(input_text):
    text_root = etree.HTML(input_text)
    if text_root is None:
        return None
    text = " ".join(text_root.itertext())
    text = re.sub(" +", " ", text)
    text = text.encode("ascii", "xmlcharrefreplace").decode("utf-8")
    text = html.unescape(text)
    return text


def normalize_answer(s):
    def remove_articles(text):
        regex = re.compile(r"\b(a|an|the)\b", re.UNICODE)
        return re.sub(regex, " ", text)

    def white_space_fix(text):
        return " ".join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    def remove_tilda(text):
        return text.replace("\n", "").replace("~", "").strip()

    return remove_tilda(white_space_fix(remove_articles(remove_punc(lower(s)))))


def get_full_question(question):
    question_text = ""
    if "name_markup" in question.keys():
        extracted_text = extract_text(question["name_markup"])
        if extracted_text is not None:
            question_text += extracted_text + " "
    if "text_markup" in question.keys():
        extracted_text = extract_text(question["text_markup"])
        if extracted_text is not None:
            question_text += extracted_text
    return question_text


def get_full_answer(answer):
    answer_text = ""
    if "text_markup" in answer.keys():
        extracted_text = extract_text(answer["text_markup"])
        if extracted_text is not None:
            answer_text += extracted_text
    return answer_text


def generate_new_datapoint(line, dataset):
    dataset[line["URI"]] = {
        "Language": line["Language"],
        "Fasttext_language": line["Fasttext_language"],
        "URI": line["URI"],
        "UUID": line["UUID"],
        "WARC_ID": line["WARC_ID"],
    }
    dataset[line["URI"]]["Questions"] = {}
    for question in line["Questions"]:
        condensed_question = copy.copy(question)
        # Remove answers to only look at questions
        condensed_question.pop("Answers")
        dataset[line["URI"]]["Questions"][
            normalize_answer(get_full_question(condensed_question))
        ] = condensed_question
        dataset[line["URI"]]["Questions"][
            normalize_answer(get_full_question(condensed_question))
        ]["Answers"] = {}
        for answer in question["Answers"]:
            dataset[line["URI"]]["Questions"][
                normalize_answer(get_full_question(condensed_question))
            ]["Answers"][normalize_answer(get_full_answer(answer))] = answer
    return dataset


def update_datapoint(line, dataset):
    curr_object = dataset[line["URI"]]
    for new_question in line["Questions"]:
        new_question_text = get_full_question(new_question)
        if len(new_question_text) > 0:
            new_question_text = normalize_answer(new_question_text)
            if new_question_text in curr_object["Questions"].keys():
                for new_answer in new_question["Answers"]:
                    new_answer_text = get_full_answer(new_answer)
                    if len(new_answer_text) > 0:
                        new_answer_text = normalize_answer(new_answer_text)
                        if (
                            new_answer_text
                            not in curr_object["Questions"][new_question_text][
                                "Answers"
                            ]
                        ):
                            curr_object["Questions"][new_question_text]["Answers"][
                                new_answer_text
                            ] = new_answer
            else:
                condensed_question = copy.copy(new_question)
                condensed_question.pop("Answers")
                curr_object["Questions"][
                    normalize_answer(get_full_question(condensed_question))
                ] = condensed_question
                dataset[line["URI"]]["Questions"][
                    normalize_answer(get_full_question(condensed_question))
                ]["Answers"] = {}
                for answer in new_question["Answers"]:
                    curr_object["Questions"][
                        normalize_answer(get_full_question(condensed_question))
                    ]["Answers"][normalize_answer(get_full_answer(answer))] = answer
    return dataset


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge duplicate URL questions and answers into single objects"
    )
    parser.add_argument("--json_dataset_path", help="Path to the json dataset")
    parser.add_argument("--output_path", help="Path to the output file")
    args = parser.parse_args()
    dataset_path = args.json_dataset_path

    with open(dataset_path, "r") as data_file:
        dataset = {}
        for idx, line in enumerate(data_file):
            line = json.loads(line)
            # Add in dictionary format for better runtime
            if line["URI"] not in dataset.keys():
                dataset = generate_new_datapoint(line, dataset)
            else:
                dataset = update_datapoint(line, dataset)

    # Save in original format
    with open(args.output_path, "w") as f:
        for url in dataset.keys():
            data_object = {
                "Language": dataset[url]["Language"],
                "Fasttext_language": dataset[url]["Fasttext_language"],
                "URI": dataset[url]["URI"],
                "UUID": dataset[url]["UUID"],
                "WARC_ID": dataset[url]["WARC_ID"],
            }
            data_object["Questions"] = []
            questions = [
                dataset[url]["Questions"][key]
                for key in dataset[url]["Questions"].keys()
            ]
            for question in questions:
                answers = [
                    question["Answers"][key] for key in question["Answers"].keys()
                ]
                question.pop("Answers")
                data_object["Questions"].append(question)
                data_object["Questions"][-1]["Answers"] = answers
            json_record = json.dumps(data_object)
            f.write(json_record + "\n")
