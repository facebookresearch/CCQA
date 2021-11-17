# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import html
import json
import argparse
import os
import random
import re
import time

from lxml import etree


def extract_text(input_text, keep_markup):
    if keep_markup:
        text = input_text.encode("ascii", "xmlcharrefreplace").decode("utf-8")
        text = html.unescape(input_text)
        text = text.replace("\n", "~").replace("\r", "~")
    elif not keep_markup:
        text_root = etree.HTML(input_text)
        if text_root is None:
            return None
        text = " ".join(text_root.itertext())
        text = re.sub(" +", " ", text)
        text = text.encode("ascii", "xmlcharrefreplace").decode("utf-8")
        text = html.unescape(text)
        text = text.replace("\n", "~").replace("\r", "~")
    return text


def clean_votes(vote):
    try:
        vote = int(vote)
    except Exception:
        try:
            vote = vote.replace(" ", "").replace("~", "")
            vote = int(vote)
        except Exception:
            try:
                vote = re.sub("/[^0-9.]/g", "", vote)
                vote = int(vote)
            except Exception:
                vote = 0
    return vote


def find_markup_options(answers):
    contains_accepted = False
    contains_suggested = False
    contains_vote = False
    for answer in answers:
        if "text_markup" in answer.keys():
            if "status" in answer.keys() and answer["status"] == "acceptedAnswer":
                contains_accepted = True
            if "status" in answer.keys() and answer["status"] == "suggestedAnswer":
                contains_suggested = True
            if "upvote_count" in answer.keys():
                contains_vote = True
    return contains_accepted, contains_suggested, contains_vote


def clean_answer(acc_answers, sugg_answers):
    cleaned_acc_answers, cleaned_sugg_answers = [], []
    if sugg_answers is not None and len(sugg_answers) > 0:
        for answer in sugg_answers:
            if answer is not None and len(answer) > 0:
                cleaned_sugg_answers.append(answer)
    if acc_answers is not None and len(acc_answers) > 0:
        has_non_empty_answer = False
        for answer in acc_answers:
            if answer is not None and len(answer) > 0:
                has_non_empty_answer = True
                cleaned_acc_answers.append(answer)
    return cleaned_acc_answers, cleaned_sugg_answers, has_non_empty_answer


def full_info(answers, question_text, keep_markup):
    acc_answers, sugg_answers = [], []
    for answer in answers:
        if answer["status"] == "acceptedAnswer":
            if "text_markup" in answer.keys():
                answer_text = extract_text(answer["text_markup"], keep_markup)
                acc_answers.append(answer_text)
        if answer["status"] == "suggestedAnswer":
            if "upvote_count" in answer.keys():
                if int(clean_votes(answer["upvote_count"])) < 2:
                    if "text_markup" in answer.keys():
                        answer_text = extract_text(answer["text_markup"], keep_markup)
                        sugg_answers.append(answer_text)
                if int(clean_votes(answer["upvote_count"])) >= 2:
                    if "text_markup" in answer.keys():
                        answer_text = extract_text(answer["text_markup"], keep_markup)
                        acc_answers.append(answer_text)
    acc_answers, sugg_answers, has_non_empty_answer = clean_answer(
        acc_answers, sugg_answers
    )
    if acc_answers is not None and len(acc_answers) > 0:
        if has_non_empty_answer:
            return {
                "question": question_text,
                "answers": [],
                "positive_ctxs": [
                    {"title": "", "text": acc_answer} for acc_answer in acc_answers
                ],
                "hard_negative_ctxs": [
                    {"title": "", "text": sugg_answer} for sugg_answer in sugg_answers
                ],
            }


def acc_sugg_info(answers, question_text, keep_markup):
    acc_answers, sugg_answers = [], []
    for answer in answers:
        if answer["status"] == "acceptedAnswer":
            if "text_markup" in answer.keys():
                answer_text = extract_text(answer["text_markup"], keep_markup)
                acc_answers.append(answer_text)
        if answer["status"] == "suggestedAnswer":
            if "text_markup" in answer.keys():
                answer_text = extract_text(answer["text_markup"], keep_markup)
                sugg_answers.append(answer_text)
    acc_answers, sugg_answers, has_non_empty_answer = clean_answer(
        acc_answers, sugg_answers
    )
    if acc_answers is not None and len(acc_answers) > 0:
        if has_non_empty_answer:
            return {
                "question": question_text,
                "answers": [],
                "positive_ctxs": [
                    {"title": "", "text": acc_answer} for acc_answer in acc_answers
                ],
                "hard_negative_ctxs": [
                    {"title": "", "text": sugg_answer} for sugg_answer in sugg_answers
                ],
            }


def vote_info(answers, question_text, keep_markup):
    best_up_count = -999
    top_answers = []
    top_answer = None
    bottom_answers = []
    for idx, answer in enumerate(answers):
        if "upvote_count" in answer.keys():
            if int(clean_votes(answer["upvote_count"])) > best_up_count:
                if "text_markup" in answer.keys():
                    answer_text = extract_text(answer["text_markup"], keep_markup)
                    top_answer = answer_text
                    best_up_count = int(clean_votes(answer["upvote_count"]))
                    best_idx = idx
    if top_answer is None:
        for idx, answer in enumerate(answers):
            if "text_markup" in answer.keys():
                answer_text = extract_text(answer["text_markup"], keep_markup)
                top_answer = answer_text
                best_idx = idx
    top_answers.append(top_answer)
    answers.pop(best_idx)
    for answer in answers:
        if "upvote_count" in answer.keys():
            if int(clean_votes(answer["upvote_count"])) > 1:
                if "text_markup" in answer.keys():
                    answer_text = extract_text(answer["text_markup"], keep_markup)
                    top_answers.append(answer_text)
            else:
                if "text_markup" in answer.keys():
                    answer_text = extract_text(answer["text_markup"], keep_markup)
                    bottom_answers.append(answer_text)
    top_answers, bottom_answers, has_non_empty_answer = clean_answer(
        top_answers, bottom_answers
    )
    if top_answers is not None and len(top_answers) > 0:
        if has_non_empty_answer:
            return {
                "question": question_text,
                "answers": [],
                "positive_ctxs": [
                    {"title": "", "text": top_answer} for top_answer in top_answers
                ],
                "hard_negative_ctxs": [
                    {"title": "", "text": bottom_answer}
                    for bottom_answer in bottom_answers
                ],
            }


def no_info(answers, question_text, keep_markup):
    random.Random(13).shuffle(answers)
    selected_answer = ""
    for answer in answers:
        if "text_markup" in answer.keys():
            answer_text = extract_text(answer["text_markup"], keep_markup)
            selected_answer = answer_text
            break
    if selected_answer is not None and len(selected_answer) > 0:
        return {
            "question": question_text,
            "answers": [],
            "positive_ctxs": [{"title": "", "text": selected_answer}],
            "hard_negative_ctxs": [],
        }


def generate_passage_retrieval_files(data_path, only_english, keep_markup, output_path):
    instances = []
    with open(data_path, "r") as f:
        for website in f:
            # Process the question
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
                # If question exists, check the answers for their markup capacities
                if len(question_text) > 0:
                    accepted, suggested, vote = find_markup_options(question["Answers"])
                    # All information available
                    if accepted and suggested and vote:
                        instances.append(
                            full_info(question["Answers"], question_text, keep_markup)
                        )
                    # If no votes are available, pick at random from accepted and suggested
                    elif accepted and suggested:
                        instances.append(
                            acc_sugg_info(
                                question["Answers"], question_text, keep_markup
                            )
                        )
                    # If only votes are available use above/below 2
                    elif vote:
                        instances.append(
                            vote_info(question["Answers"], question_text, keep_markup)
                        )
                    # Otherwise just select one at random to be a positive ctx and no hard negatives
                    else:
                        instances.append(
                            no_info(question["Answers"], question_text, keep_markup)
                        )

    with open(output_path + ".jsonl", "w") as f:
        for sample in instances:
            json_record = json.dumps(sample)
            f.write(json_record + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate passage retrieval objects for open-book QA"
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
    generate_passage_retrieval_files(
        args.data_path, args.only_english, args.keep_markup, args.output_path
    )
