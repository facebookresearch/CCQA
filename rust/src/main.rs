// Copyright (c) Facebook, Inc. and its affiliates.
// All rights reserved.
//
// This source code is licensed under the license found in the
// LICENSE file in the root directory of this source tree.

extern crate clap;
extern crate kuchiki;

use kuchiki::traits::*;
use kuchiki::NodeRef;

use indicatif::ParallelProgressIterator;
use lazy_static::lazy_static;
use regex::Regex;
use std::borrow::Cow;
use std::fs::OpenOptions;
use std::io::prelude::*;
use std::time::Instant;

use clap::{App, Arg};
use rayon::iter::ParallelIterator;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use warc::header::WarcHeader;
use warc::{RawRecord, WarcReader};

#[derive(Serialize, Deserialize, Debug)]
struct HTMLMinified {
    mhtml: String,
    language: String,
    uri: String,
    ip_address: String,
}

pub(crate) fn warc_to_dom(record: &RawRecord) -> Option<(String, String, String, NodeRef)> {
    let target_uri = WarcHeader::TargetURI;
    let uri = String::from_utf8_lossy(&record.headers[&target_uri]).to_string();
    let target_ip = WarcHeader::IPAddress;
    let ip = String::from_utf8_lossy(&record.headers[&target_ip]).to_string();
    let document_string = String::from_utf8_lossy(&record.body);
    let document_string_ref = document_string.as_ref();
    let document_strip_crawler = document_string_ref.splitn(2, "\r\n\r\n");
    let document_splits = document_strip_crawler.into_iter().collect::<Vec<&str>>();
    if document_splits.len() != 2 {
        return None;
    }
    Some((
        uri,
        ip,
        document_splits[1].to_string(),
        kuchiki::parse_html().one(document_splits[1]),
    ))
}

fn contains_question(text: &str) -> bool {
    lazy_static! {
        static ref RE: Regex = Regex::new(r".*?https://schema.org/Question.*?").unwrap();
    }
    RE.is_match(text)
}

pub fn is_emptyspace(c: char) -> bool {
    c == ' ' || c == ' ' || c == '\t' || c == '\n'
}

// Borrowed and changed from https://github.com/lise-henry/crowbook-text-processing/blob/master/src/lib/clean.rs
pub fn emptyspaces<'a, S: Into<Cow<'a, str>>>(input: S) -> Cow<'a, str> {
    let regex = Regex::new(r"[  \x{202F}\x{2002}\t\n]{2,}?").unwrap();
    let input = input.into();
    let first = regex.find(&input).map(|mat| mat.start());
    if let Some(first) = first {
        let mut new_s = String::with_capacity(input.len());
        new_s.push_str(&input[0..first]);
        let mut previous_space = false;
        for c in input[first..].chars() {
            if is_emptyspace(c) {
                if previous_space {
                    // previous char already a space, don't copy it
                } else {
                    new_s.push(c);
                    previous_space = true;
                }
            } else {
                previous_space = false;
                new_s.push(c);
            }
        }
        Cow::Owned(new_s)
    } else {
        input
    }
}

fn reduce_tilde(input: String) -> String {
    lazy_static! {
        static ref RR: Regex = Regex::new(r"~+").unwrap();
    }
    let out = RR.replace_all(&input, "~");
    return out.to_string();
}

fn reduce_breaks(input: String) -> String {
    lazy_static! {
        static ref RR: Regex = Regex::new(r"(<br>)+").unwrap();
    }
    let out = RR.replace_all(&input, "<br>");
    return out.to_string();
}

fn find_lang_tag(node: NodeRef) -> Option<String> {
    if let kuchiki::NodeData::Element(x) = node.data() {
        if x.name.local == "html".to_string() {
            let x_attr = (x.attributes).clone().into_inner();
            if x_attr.contains("lang") {
                return Some(x_attr.get("lang").unwrap().to_string());
            }
        }
    }
    for child in node.children() {
        let result = find_lang_tag(child.clone());
        if let Some(_) = result {
            return result;
        }
    }
    return None;
}

fn transform_outside(node: NodeRef) -> Option<Vec<NodeRef>> {
    // Pre order traversal
    if let kuchiki::NodeData::Element(x) = node.data() {
        let x_attr = (x.attributes).clone().into_inner();
        if x_attr.contains("itemtype") {
            let itemtype = x_attr.get("itemtype").unwrap();
            if itemtype == "https://schema.org/Question" {
                let mut vec = Vec::new();
                vec.push(node.clone());
                return Some(vec);
            }
        }
    }
    let mut vec = Vec::new();
    for child in node.children() {
        let tmp_vec = transform_outside(child.clone());
        if let Some(x) = tmp_vec {
            vec.extend(x);
        }
    }
    if vec.len() > 0 {
        return Some(vec);
    } else {
        return None;
    }
}

fn inside_props(node: NodeRef) {
    // Post order traversal
    for child in node.children() {
        inside_props(child.clone());
    }
    if let kuchiki::NodeData::Element(x) = node.data() {
        let mut x_attr = (x.attributes).borrow_mut();

        // Remove empty and not item-related attributes
        for (key, value) in x_attr.clone().map.into_iter() {
            if !(key.local.starts_with("item")
                || key.local.starts_with("content")
                || key.local.starts_with("date"))
            {
                x_attr.remove(key.local);
            } else {
                if value.value.len() < 1 {
                    x_attr.remove(key.local);
                }
            }
        }

        // Remove media tags
        if x.name.local.contains("svg")
            || x.name.local.contains("img")
            || x.name.local.contains("hatul")
            || x.name.local.contains("input")
            || x.name.local.contains("button")
            || x.name.local.contains("link")
        {
            for child in node.children() {
                node.insert_after(child)
            }
            node.detach();
        }

    // Clean the text elements
    } else if let kuchiki::NodeData::Text(x) = node.data() {
        let mut clean: String = x.borrow().to_string();
        clean = clean_text(clean);
        x.replace(clean.clone());
    }
}

fn clean_text(mut clean: String) -> String {
    clean = clean.replace("\n", "~");
    clean = emptyspaces(clean).into();
    clean = clean.trim_end().trim_start().to_string();
    let clean = html_escape::encode_text(&clean).into();
    return clean;
}

// Remove all nodes recusively bottom-up if the don't contain textual information
fn remove_empty_nodes(node: NodeRef) -> bool {
    // Post order traversal
    for child in node.children() {
        remove_empty_nodes(child.clone());
    }
    // Remove nodes without children that are not part of the item* family
    if let kuchiki::NodeData::Element(x) = node.data() {
        let local_attrs = x.clone().attributes.into_inner();
        if &node.children().count() == &0
            // If no content inside, it needs a content attribute with data or be a <br> tag
            && !(local_attrs.contains("itemprop") && local_attrs.contains("content"))
            && !(local_attrs.contains("itemtype") && local_attrs.contains("content"))
            && !(x.name.local == "br".to_string())
        {
            node.detach();
            return false;
        }
    } else if let kuchiki::NodeData::Text(x) = node.data() {
        let text: String = x.borrow().to_string();
        if &text.len() < &1 || &text == &"~" || &text == &" " {
            node.detach();
            return false;
        }
    }
    return true;
}

fn transform_inside(node: NodeRef) {
    let local_attrs: kuchiki::Attributes;
    if let kuchiki::NodeData::Element(x) = node.data() {
        local_attrs = x.clone().attributes.into_inner();
        {
            let mut x_attr = (x.attributes).borrow_mut();
            for (key, value) in x_attr.clone().map.into_iter() {
                // Remove all parameters that are not schema.org related
                if !(key.local.starts_with("item")
                    || key.local.starts_with("content")
                    || key.local.starts_with("date"))
                {
                    x_attr.remove(key.local);
                } else {
                    if value.value.len() < 1 {
                        x_attr.remove(key.local);
                    }
                }
            }
        }
        // Clean indide schema.org/Question tags
        if local_attrs.contains("itemprop") && !local_attrs.contains("itemtype") {
            if local_attrs.get("itemprop").unwrap() == "url" {
                node.detach();
            } else {
                inside_props(node.clone());
                remove_empty_nodes(node.clone());
                return;
            }
        }
    }
    // Post order traversal
    for child in node.children() {
        transform_inside(child.clone());
    }
    if let kuchiki::NodeData::Element(x) = node.data() {
        let x_attr = x.clone().attributes.into_inner();
        if !x_attr.contains("itemtype") && !x_attr.contains("itemprop") {
            for child in node.children() {
                node.insert_after(child)
            }
            node.detach();
        }
    } else {
        node.detach();
    }
}

fn minify(file_path: &str) -> Vec<HTMLMinified> {
    // Processing a single webpage
    let single_record_processor = |record: &RawRecord| -> Option<HTMLMinified> {
        // Remove all documents without the Question schema before generating the DOM to speed up processing
        let doc_string = String::from_utf8_lossy(&record.body);
        if !contains_question(&doc_string) {
            return None;
        }
        // Generate DOM, retrieve URI and ip-address
        let (uri, ip, _, document) = warc_to_dom(record)?;
        // Find language
        let mut language: String = "-".to_string();
        if let Some(x) = find_lang_tag(document.clone()) {
            language = x;
        }
        // Remove everything outside of Question
        let outside_result = transform_outside(document);
        if outside_result.is_none() {
            return None;
        }
        let questions = outside_result.unwrap();
        // Remove everything without item* attribute inside
        let mut cleaned_questions = Vec::new();
        for question in questions {
            transform_inside(question.clone());
            remove_empty_nodes(question.clone());
            // Remove newline and carriage returns from the data to avoid additional linebreaks
            let mut string_question = question.to_string().replace("\n", "").replace("\r", "");
            string_question = reduce_tilde(string_question);
            string_question = reduce_breaks(string_question);
            cleaned_questions.push(string_question);
        }
        let all_questions: String = cleaned_questions.into_iter().collect();
        // Return a minified mhtml object
        Some(HTMLMinified {
            mhtml: all_questions,
            language,
            uri,
            ip_address: ip,
        })
    };

    let from_start = Instant::now();
    let file = WarcReader::from_path(file_path).unwrap();
    let file_output = file.collect::<Vec<Result<RawRecord, warc::Error>>>();
    // Read WARC file and collect all well formatted webpages
    let file_error_filter_out = file_output
        .iter()
        .filter(|x| x.is_ok())
        .map(|x| x.as_ref().unwrap())
        .collect::<Vec<&RawRecord>>();
    println!(
        "Finished Reading in {} ms",
        from_start.elapsed().as_millis()
    );

    // Parallel process WARC file
    let from_process = Instant::now();
    let file_output_length = file_output.len() as u64;
    println!("{}", file_output_length);
    let (oks, _): (Vec<_>, Vec<_>) = file_error_filter_out
        .into_par_iter()
        .progress_count(file_output_length)
        .map(single_record_processor)
        .partition(Option::is_some);
    println!(
        "Finished Processing in {} ms for a throughput of {} per ms",
        from_process.elapsed().as_millis(),
        (file_output_length as u128) / from_process.elapsed().as_millis()
    );
    println!(
        "Finished End to End in {} ms, for a throughput of {} per ms",
        from_start.elapsed().as_millis(),
        (file_output_length as u128) / from_start.elapsed().as_millis()
    );

    // Clean out empty webpages
    oks.into_iter()
        .map(Option::unwrap)
        .filter(|x| x.mhtml.len() > 0)
        .collect::<Vec<HTMLMinified>>()
}

// Entry point
fn main() -> std::io::Result<()> {
    let matches = App::new("CCQA WARC Processor")
        .version("1.0")
        .author("Patrick Huber <huberpat@cs.ubc.ca> and Armen Aghajanyan <armenag@fb.com>")
        .about("Common Crawl Question Answering (CCQA) WARC processor for in-domain pre-training corpora")
        .arg(
            Arg::with_name("input_file")
                .help("WARC input file")
                .required(true)
                .index(1),
        )
        .arg(
            Arg::with_name("output_file")
                .help("Minified HTML (mhtml) output file path")
                .required(true)
                .index(2),
        )
        .get_matches();

    let file_path = matches.value_of("input_file").unwrap();
    let output_file_path = matches.value_of("output_file").unwrap();
    // Main function of the script called here
    let minified = minify(file_path);
    let json_val = serde_json::to_string_pretty(&minified)?;
    match OpenOptions::new()
        .create(true)
        .write(true)
        .append(false)
        .open(output_file_path)
    {
        Ok(ref mut file) => {
            file.write_all(json_val.as_bytes())?;
        }
        Err(err) => {
            panic!("Failed to open output file: {}", err);
        }
    }
    Ok(())
}
