# CCQA: A New Web-Scale Question Answering Dataset for Model Pre-Training

This is the official repository for the code and models of the paper _CCQA: A New Web-Scale Question Answering Dataset for Model Pre-Training_.
If you use our dataset, code or any parts thereof, please cite this paper:

    @misc{huber-etal-2021-ccqa,
      title={CCQA: A New Web-Scale Question Answering Dataset for Model Pre-Training}, 
      author={Patrick Huber and Armen Aghajanyan and Barlas Oğuz and Dmytro Okhonko and Wen-tau Yih and Sonal Gupta and Xilun Chen},
      year={2021},
      eprint={2110.07731},
      archivePrefix={arXiv},
      primaryClass={cs.CL}
    }


Getting Common Crawl Snapshots
===
The Common Crawl project provides monthly web snapshots of new and updates websites in raw HTML format.
Every monthly snapshot (~50-70TB) is further separated into smaller WARC (Web ARChive) files.
To download a single WARC file, go to the [Common Crawl website](https://commoncrawl.org) for the respective month (e.g. [May 2021](https://commoncrawl.org/2021/05/may-2021-crawl-archive-now-available/)) and download the [WARC paths file](https://commoncrawl.s3.amazonaws.com/crawl-data/CC-MAIN-2021-21/warc.paths.gz).
The downloaded [WARC paths file](https://commoncrawl.s3.amazonaws.com/crawl-data/CC-MAIN-2021-21/warc.paths.gz) contains a \newline separated list of download destination of the actual files.
Pick a path and prepend [**s3://commoncrawl/**](s3://commoncrawl/) or **https://commoncrawl.s3.amazonaws.com/** for the complete URL. Once downloaded, gunzip the archive and a single Common Crawl web archive is ready to be processed.


Dataset Generation
===

## Dependencies
Below are the required dependencies to run the dataset generation, curation and model evaluations.
* [Rust](https://www.rust-lang.org/learn/get-started)
* Rust packages: clap, html-escape, indicatif, kuchiki, rayon, regex, serde, serde_json, warc (see Cargo.toml file for versions)
* Python 3.7.3
* Python dependencies: [fasttext language identification](https://fasttext.cc/blog/2017/10/02/blog-post.html), fasttext==0.9.2, lxml==4.3.2

## Processing Common Crawl data (Rust)
* Build the cargo package with `cargo build` from within the rust folder
* Run the script with `cargo run <path/to/warc/file> <path/to/output/file.mhtml>`

## Curating the minified HTML data (Python)
To generate json objects for every webpage in the minified HTML, run

`python mhtml_to_json.py <path/to/fasttext/lid.176.bin> <path/to/mhtml/file> <path/to/output/file>`

## Aggregating datapoints to remove duplicate URL entries (Python)
As mentioned in the paper, we use the original dataset for our in-domain pre-training experiments.
However, we also provide a cleaned version of the dataset, aggregating same-URL duplicates into a single object.
To run the datapoint aggregation script, execute

`python json_duplicate_filter.py <path/to/json/file> <path/to/output/file>`

## Converting json dataset into closed-book and passage retrieval formats (Python)
To be able to train closed-book (sequence-to-sequence) and passage retrieval (DPR) models on the CCQA dataset, the corpus needs to be further processed

### Closed-book processing
To prepare the dataset for closed-book question-answering training, run:

`python closed_book_processing.py <path/to/json/file> <path/to/output/file> <--only_english> <--keep_markup>`

### Passage retrieval (DPR) processing
To prepare the dataset for passage rertieval (DPR) training, run:

`python passage_retrieval_processing.py <path/to/json/file> <path/to/output/file> <--only_english> <--keep_markup>`


CCQA In-Domain Pre-Trained Model Checkpoints
===

BART and T5 checkpoints are Huggingface transformer models tested with [transformers version 4.8.2](https://huggingface.co/transformers/v4.8.2/)

* [BART-Large (seq2seq)](https://dl.fbaipublicfiles.com/CCQA/models/bart_large_ccqa_seq2seq_pretrained/pytorch_model.bin)
* [BART-Large (denoising)](https://dl.fbaipublicfiles.com/CCQA/models/bart_large_ccqa_denoising_pretrained/pytorch_model.bin)
* [T5 Small](https://dl.fbaipublicfiles.com/CCQA/models/t5_small_ccqa_pretrained/pytorch_model.bin)
* [T5 Base](https://dl.fbaipublicfiles.com/CCQA/models/t5_base_ccqa_pretrained/pytorch_model.bin)

The DPR model checkpoint can be downloaded for the [original DPR codebase](https://github.com/facebookresearch/DPR) or the [DPR v2 codebase](https://github.com/facebookresearch/dpr-scale)

* [DPR original](https://dl.fbaipublicfiles.com/CCQA/models/bert_base_dpr_pretrained/bert_base_dpr_original_codebase.ckpt)
* [DPR v2](https://dl.fbaipublicfiles.com/CCQA/models/bert_base_dpr_pretrained/bert_base_dpr_updated_codebase.ckpt)


# LICENSE
The majority of CCQA is licensed under CC-BY-NC, however portions of the project are available under separate license terms: crowbook-text-processing is licensed under the MPL-2.0 license.
