# Copyright (c) 2019, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""several datasets with preset arguments"""
from .datasets import json_dataset, csv_dataset
import os
import json
import random
import tqdm
from multiprocessing import Queue, Process
from torch.utils import data
from .lazy_loader import lazy_array_loader

NUM_PROCESSES = 40

class webtext(json_dataset):
    """
    dataset for webtext with arguments configured for convenience

    command line usage: `--train-data webtext`
    """
    PATH = 'data/webtext/data.json'
    assert_str = "make sure to set PATH for webtext data_utils/corpora.py"

    def __init__(self, **kwargs):
        assert os.path.exists(webtext.PATH), \
            webtext.assert_str
        if not kwargs:
            kwargs = {}
        kwargs['text_key'] = 'text'
        kwargs['loose_json'] = True
        super(webtext, self).__init__(webtext.PATH, **kwargs)


class PromptDataset(data.Dataset):
    def __init__(self, prompt_loader, text_loader, tokenizer=None, to_tokenize=False, **kwargs):
        self.prompts = prompt_loader
        self.texts = text_loader
        self.tokenizer = tokenizer
        self.to_tokenize = to_tokenize
        if isinstance(self.prompts, lazy_array_loader) and isinstance(self.texts, lazy_array_loader):
            self.prompt_lens = self.prompts.lens
            self.text_lens = self.texts.lens
            self.is_lazy = True

    def get_text_len(self, idx):
        return self.prompt_lens[idx] + self.text_lens[idx]

    def process_line(self, data):
        raise NotImplementedError

    def __getitem__(self, index):
        prompt = self.prompts[index]
        text = self.texts[index]
        if self.to_tokenize:
            prompt = self.tokenizer.EncodeAsIds(prompt).tokenization
            text = self.tokenizer.EncodeAsIds(text).tokenization
        return {"tokens": prompt + text, "loss_masks": [0] * len(prompt) + [1] * len(text)}

    def __len__(self):
        return len(self.prompts)


class DataReader:
    PATH = None
    assert_str = None

    @staticmethod
    def tokenize_worker(input, output, reader, tokenizer, tokenize):
        for row in iter(input.get, 'STOP'):
            data = json.loads(row)
            prompts, texts = reader.process_line(data, tokenizer, tokenize)
            for prompt, text in zip(prompts, texts):
                output.put((prompt, text))
        output.put("COMPLETE")

    def __init__(self, prompt_writer, text_writer, tokenizer=None, tokenize=False, **kwargs):
        assert os.path.exists(self.PATH), self.assert_str
        self.tokenizer = tokenizer
        self.tokenize = tokenize
        if os.path.isdir(self.PATH):
            paths = [entry.path for entry in os.scandir(self.PATH) if not entry.is_dir() and not entry.name.endswith("bz2")]
        else:
            paths = [self.PATH]
        task_queue, done_queue = Queue(), Queue()
        processes = []
        for i in range(NUM_PROCESSES):
            process = Process(target=self.tokenize_worker,
                              args=(task_queue, done_queue, type(self), tokenizer, tokenize))
            process.start()
            processes.append(process)
        for path in paths:
            with open(path) as file:
                for row in tqdm.tqdm(file):
                    task_queue.put(row)
        for i in range(len(processes)):
            task_queue.put('STOP')
        count = len(processes)
        progress_bar = tqdm.tqdm()
        while True:
            data = done_queue.get()
            if data == 'COMPLETE':
                count -= 1
                if count == 0:
                    break
            else:
                prompt, text = data
                prompt_writer.write(prompt)
                text_writer.write(text)
                progress_bar.update()
        progress_bar.close()

    @staticmethod
    def get_token_count(contents):
        return sum(map(len, contents))

    @staticmethod
    def process_sample(prompt, text, tokenizer, tokenize):
        if isinstance(prompt, str) and tokenize:
            prompt = tokenizer.EncodeAsIds(prompt).tokenization if prompt else []
        if isinstance(text, str) and tokenize:
            text = tokenizer.EncodeAsIds(text).tokenization if text else []
        return prompt, text

    @staticmethod
    def trim_field(content, max_length):
        if len(content) > max_length:
            content = content[:max_length]
            content += "......"
        return content

    @classmethod
    def process_line(cls, data, tokenizer, tokenize):
        raise NotImplementedError


class zhihu(DataReader):
    PATH = "/root/data/zhihu/zhihu"
    # PATH = "data/zhihu/data.json"
    assert_str = "make sure to set PATH for zhihu data_utils/corpora.py"
    qtitle_prefix = "问题："
    qcontent_prefix = "问题描述："
    user_prefix = "回答用户："
    answer_prefix = " 回答："
    # qtitle_prefix = []
    # qcontent_prefix = []
    # user_prefix = []
    # answer_prefix = []

    @classmethod
    def process_line(cls, data, tokenizer, tokenize):
        prompts, texts = [], []
        ans_length = len(data.get("ans-content", ""))
        ans_up = data.get("ans-up-num", "")
        ans_up = int(ans_up) if ans_up else 0
        if ans_length > 100 or ans_up > 1000:
            qtitle = data["q_title"]
            qcontent = data["q-content"]
            if qcontent is None:
                qcontent = ""
            qcontent = cls.trim_field(qcontent, max_length=100)
            user = data.get("user-signature", "")
            prompt = cls.qtitle_prefix + qtitle + cls.qcontent_prefix + qcontent + cls.user_prefix + user + cls.answer_prefix
            text = data["ans-content"]
            prompt, text = cls.process_sample(prompt, text, tokenizer, tokenize)
            prompts.append(prompt)
            texts.append(text)
        # prompt = data["q_title"] + data["q-content"] + data["user-signature"]
        # text = data["ans-content"]
        # prompts.append(prompt)
        # texts.append(text)
        return prompts, texts


class zhidao(DataReader):
    PATH = "/root/data/zhidao/zhidao"
    assert_str = "make sure to set PATH for zhidao data_utils/corpora.py"
    qtitle_prefix = "问题："
    qcontent_prefix = "问题描述："
    answer_prefix = "回答："

    @classmethod
    def process_line(cls, data, tokenizer, tokenize):
        if "title" not in data:
            return [], []
        prompts, texts = [], []
        qtitle = data["title"]
        qcontent = data.get("content", "")
        qcontent = cls.trim_field(qcontent, max_length=100)
        prompt = cls.qtitle_prefix + qtitle + cls.qcontent_prefix + qcontent + cls.answer_prefix
        if "best_answer" in data:
            text = data["best_answer"]["content"]
            if len(text) > 10:
                p, t = cls.process_sample(prompt, text, tokenizer, tokenize)
                prompts.append(p)
                texts.append(t)
        for answer in data.get("other_answers", []):
            text = answer["content"]
            if len(text) > 100:
                p, t = cls.process_sample(prompt, text, tokenizer, tokenize)
                prompts.append(p)
                texts.append(t)
        return prompts, texts


class baike(DataReader):
    PATH = "/root/data/baike/baike"
    assert_str = "make sure to set PATH for baike data_utils/corpora.py"

    @classmethod
    def process_line(cls, data, tokenizer, tokenize):
        prompts, texts = [], []
        text = data.get("title", "") + data.get("abstract", "") + data.get("content", "")
        if text:
            p, t = cls.process_sample("", text, tokenizer, tokenize)
            prompts.append(p)
            texts.append(t)
        return prompts, texts


class wikipedia(DataReader):
    """
    dataset for wikipedia with arguments configured for convenience

    command line usage: `--train-data wikipedia`
    """
    # PATH = '/dataset/data/wiki.txt'
    PATH = '/root/data/wikipedia/wiki.txt'
    assert_str = "make sure to set PATH for wikipedia data_utils/corpora.py"

    @classmethod
    def process_line(cls, data, tokenizer, tokenize):
        text = data['text']
        prompt, text = cls.process_sample("", text, tokenizer, tokenize)
        return [prompt], [text]



NAMED_CORPORA = {
    'wikipedia': wikipedia,
    'webtext': webtext,
    "zhihu": zhihu,
    "zhidao": zhidao,
    "baike": baike
}
