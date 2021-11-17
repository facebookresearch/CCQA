#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import html
import json
import multiprocessing
import os
import time
import uuid

import fasttext
import lxml.html
from lxml import etree


def collect_question(node):
    question = {}
    # name
    name_node = find_itemprop(node, "name")
    if name_node is not None:
        name_node = text_cleanup(name_node)
        question["name_markup"] = turn_into_string(name_node)

    # text
    text_node = find_itemprop(node, "text")
    if text_node is not None:
        text_node = text_cleanup(text_node)
        question["text_markup"] = turn_into_string(text_node)

    # date/time {created|modified|published}
    date_created = find_itemprop(node, "dateCreated")
    if date_created is not None:
        date_created = date_created.get("datetime")
        question["date_created"] = date_created
    date_modified = find_itemprop(node, "dateModified")
    if date_modified is not None:
        date_modified = date_modified.get("datetime")
        question["date_modified"] = date_modified
    date_published = find_itemprop(node, "datePublished")
    if date_published is not None:
        date_published = date_published.get("datetime")
        question["date_published"] = date_published

    # upvote count
    upvote_count = find_itemprop(node, "upvoteCount")
    if upvote_count is not None:
        if upvote_count.tag == "meta":
            upvote_count = upvote_count.get("content")
        else:
            upvote_count = upvote_count.text
        question["upvote_count"] = upvote_count

    # downvote count
    downvote_count = find_itemprop(node, "downvoteCount")
    if downvote_count is not None:
        if downvote_count.tag == "meta":
            downvote_count = downvote_count.get("content")
        else:
            downvote_count = downvote_count.text
        question["downvote_count"] = downvote_count

    # comment count
    comment_count = find_itemprop(node, "commentCount")
    if comment_count is not None:
        if comment_count.tag == "meta":
            comment_count = comment_count.get("content")
        else:
            comment_count = comment_count.text
        question["comment_count"] = comment_count

    # Answer count
    answer_count = find_itemprop(node, "answerCount")
    if answer_count is not None:
        if answer_count.tag == "meta":
            answer_count = answer_count.get("content")
        else:
            answer_count = answer_count.text
        question["answer_count"] = answer_count

    return question


def collect_answer(node):
    answer = {}
    # text
    text_node = find_itemprop(node, "text")
    if text_node is not None:
        text_node = text_cleanup(text_node)
        answer["text_markup"] = turn_into_string(text_node)

    # suggested|accepted
    suggested_accepted = node.get("itemprop")
    answer["status"] = suggested_accepted

    # date/time {created|modified|published}
    date_created = find_itemprop(node, "dateCreated")
    if date_created is not None:
        date_created = date_created.get("datetime")
        answer["date_created"] = date_created
    date_modified = find_itemprop(node, "dateModified")
    if date_modified is not None:
        date_modified = date_modified.get("datetime")
        answer["date_modified"] = date_modified
    date_published = find_itemprop(node, "datePublished")
    if date_published is not None:
        date_published = date_published.get("datetime")
        answer["date_published"] = date_published

    # upvote count
    upvote_count = find_itemprop(node, "upvoteCount")
    if upvote_count is not None:
        if upvote_count.tag == "meta":
            upvote_count = upvote_count.get("content")
        else:
            upvote_count = upvote_count.text
        answer["upvote_count"] = upvote_count

    # downvote count
    downvote_count = find_itemprop(node, "downvoteCount")
    if downvote_count is not None:
        if downvote_count.tag == "meta":
            downvote_count = downvote_count.get("content")
        else:
            downvote_count = downvote_count.text
        answer["downvote_count"] = downvote_count

    # comment count
    comment_count = find_itemprop(node, "commentCount")
    if comment_count is not None:
        if comment_count.tag == "meta":
            comment_count = comment_count.get("content")
        else:
            comment_count = comment_count.text
        answer["comment_count"] = comment_count

    return answer


def predict_majority_language(languages):
    frequency = {}
    for language in languages:
        if language in frequency:
            frequency[language] += 1
        else:
            frequency[language] = 1
    language, appearances = "-", 0
    for key in frequency.keys():
        if frequency[key] > appearances:
            appearances = frequency[key]
            language = key
    return language


def collect_person(node):
    person = {}
    relevant_node = find_itemprop(node, "name")
    if relevant_node is None:
        # If name not defined, try author, which seems to be used sometimes
        relevant_node = find_itemprop(node, "author")
        if relevant_node is None:
            return None
    else:
        if relevant_node.tag == "meta":
            person["author"] = relevant_node.get("content")
        else:
            person["author"] = relevant_node.text
        return person


def text_cleanup(node):
    # Only keep text elements from https://developer.mozilla.org/en-US/docs/Web/HTML/Element
    valid_tags = [
        "blockquote",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "hr",
        "li",
        "ol",
        "p",
        "pre",
        "ul",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "a",
        "abbr",
        "b",
        "bdi",
        "bdo",
        "br",
        "cite",
        "code",
        "data",
        "dfn",
        "em",
        "i",
        "kbd",
        "mark",
        "q",
        "rb",
        "rp",
        "rt",
        "rtc",
        "ruby",
        "s",
        "samp",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
        "time",
        "u",
        "var",
        "wbr",
        "caption",
        "col",
        "colgroup",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
    ]
    remove_all_but_text_nodes(node, valid_tags)
    return node


def turn_into_string(node):
    text_string = lxml.html.tostring(node).decode("utf-8")
    # Remove the most outer tag, since that is the itemprop tag, which is not relevant anymore
    text_string = text_string[text_string.find(">") + 1 :]
    text_string = text_string[: text_string.rfind("</")]
    return text_string


def remove_all_but_text_nodes(node, valid_tags):
    for child in node:
        remove_all_but_text_nodes(child, valid_tags)
    if node.tag not in valid_tags and "itemprop" not in node.keys():
        for valid_child in node:
            node.addnext(valid_child)
        if node.getparent() is not None:
            node.getparent().remove(node)


def find_itemprop(node, prop):
    if "itemprop" in node.keys():
        if prop in node.get("itemprop"):
            return node
    for child in node:
        value = find_itemprop(child, prop)
        if value is not None:
            return value
    return None


def get_all_questions(node, question_list):
    if "itemtype" in node.keys():
        if "//schema.org/Question" in node.get("itemtype"):
            question_list.append(node)
            return
    for child in node:
        get_all_questions(child, question_list)


def predict_question_language(json_question, ft_model):
    if "text_markup" in json_question.keys():
        language = ft_model.predict(html.unescape(json_question["text_markup"]))[0][
            0
        ].replace("__label__", "")
    elif "name_markup" in json_question.keys():
        language = ft_model.predict(html.unescape(json_question["name_markup"]))[0][
            0
        ].replace("__label__", "")
    else:
        for answer in json_question["Answers"]:
            if "text_markup" in answer.keys():
                language = ft_model.predict(html.unescape(answer["text_markup"]))[0][
                    0
                ].replace("__label__", "")
                break
    return language


def has_at_least_Q_or_A(json_question):
    if "name_markup" in json_question.keys() or "text_markup" in json_question.keys():
        return True
    for answer in json_question["Answers"]:
        if "text_markup" in answer.keys():
            return True
    return False


def search_tree(node, json_context):
    if "itemtype" in node.keys() and "//schema.org/Answer" in node.get("itemtype"):
        if "Answers" not in json_context.keys():
            # Stacked question (not in the schema.org definition)
            if node.getparent() is not None:
                node.getparent().remove(node)
            return
        else:
            json_context["Answers"].append({})
            json_context = json_context["Answers"][-1]
    for child in node:
        search_tree(child, json_context)
    if "itemtype" in node.keys():
        if "//schema.org/Question" in node.get("itemtype"):
            if "Answers" not in json_context.keys():
                # Stacked question (not in the schema.org definition)
                if node.getparent() is not None:
                    node.getparent().remove(node)
                return
            else:
                element = collect_question(node)
                json_context.update(element)
            if node.getparent() is not None:
                node.getparent().remove(node)
        elif "//schema.org/Answer" in node.get("itemtype"):
            element = collect_answer(node)
            json_context.update(element)
            if node.getparent() is not None:
                node.getparent().remove(node)
        elif "//schema.org/Person" in node.get("itemtype"):
            element = collect_person(node)
            if element is not None:
                json_context.update(element)
            if node.getparent() is not None:
                node.getparent().remove(node)


def generate_structured_json(files, output_folder, output_file, fasttext_bin):
    ft_model = fasttext.load_model(fasttext_bin)
    for warc_file in files:
        with open(warc_file) as f, open(
            os.path.join(
                output_folder,
                output_file.replace(
                    "PLACEHOLDER", os.path.basename(warc_file).replace(".mhtml", "")
                ),
            ),
            "a+",
        ) as g:
            webpages = json.loads(f.read())
            for idx, element in enumerate(webpages):
                document = {}
                html_content = element["mhtml"]
                language = element["language"]
                uri = element["uri"]

                html_root = etree.HTML(html_content)
                html_questions, json_questions, questions_language = [], [], []
                get_all_questions(html_root, html_questions)
                for html_question in html_questions:
                    json_question = {"Answers": []}
                    search_tree(html_question, json_question)
                    # Remove everything that does not have a question name || question text || answer text for the same instance
                    has_Q_or_A = has_at_least_Q_or_A(json_question)
                    if has_Q_or_A:
                        questions_language.append(
                            predict_question_language(json_question, ft_model)
                        )
                        json_questions.append(json_question)
                if len(json_questions) > 0:
                    question_uuid = str(uuid.uuid4())
                    predicted_language = predict_majority_language(questions_language)
                    json_record = json.dumps(
                        {
                            "Language": language,
                            "Fasttext_language": predicted_language,
                            "URI": uri,
                            "UUID": question_uuid,
                            "WARC_ID": os.path.basename(warc_file).replace(
                                ".mhtml", ""
                            ),
                            "Questions": json_questions,
                        }
                    )
                    g.write(json_record + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert mhtml objects into json")
    parser.add_argument("--fasttext_path", help="Path to the fasttext lid.176.bin file")
    parser.add_argument("--input_folder", help="Path to the mhtml folder")
    parser.add_argument("--output_folder", help="Path to the output folder")
    args = parser.parse_args()

    fasttext_bin = args.fasttext_path
    input_folder = args.input_folder
    output_folder = args.output_folder
    output_file = "ccqa_PLACEHOLDER.json"

    if os.path.isfile(os.path.join(output_folder, output_file)):
        print("Output files already exist and will be replaced...")
        os.remove(os.path.join(output_folder, output_file))

    files = [
        os.path.join(input_folder, f)
        for f in os.listdir(input_folder)
        if f.endswith(".mhtml")
    ]

    generate_structured_json(files, output_folder, output_file, fasttext_bin)
