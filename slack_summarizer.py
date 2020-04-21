#!/usr/bin/env python3

import sys
import os
import requests
import re
import json
import time
import datetime
import argparse

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer
from sumy.summarizers.text_rank import TextRankSummarizer
from sumy.summarizers.lsa import LsaSummarizer 

# export SLACK_OAUTH_TOKEN=xoxb-<your-OAuth-token>  # OAuth Access Token
# export SLACK_BOT_TOKEN=xoxb-<your-bot-token> # Bot User OAuth Access Token

MAX = 100  # The maximum number of items for Conversations API
DEFAULT_CHANNEL_ID = "CXXXXXXXXXX" # <- you can find it accessing by browser
OAUTH_TOKEN = os.environ['SLACK_OAUTH_TOKEN']
BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']

def get_user_name_list(user_list):
    name = dict()
    for id in user_list:
        if id not in name:
            name[id] = get_user_name(id)
    return name

def get_user_name(user_id):
    user_info = get_user_info(user_id)
    if user_info.get('ok',False) == False:
            print('error user_id [{0}]'.format(u_id))
            print(user_info)
            return 'Error'
    if user_info['user']['is_bot'] == True:
        name = 'Bot-' + user_info['user']['real_name']
    else:
        display_name = user_info['user']['profile']['display_name']
        if display_name != '':
            name = display_name
        else:
            name = user_info['user']['name']
    return name

User_Info_API_URL = "https://slack.com/api/users.info"
def get_user_info(user_id):
    params = {'token':BOT_TOKEN,
            'user':user_id}
    r = requests.get(User_Info_API_URL, params=params)
    json_data = r.json()

    return json_data


# 履歴の表示
Conversations_History_API_URL = "https://slack.com/api/conversations.history"
def get_history(channel_id, limit, options):
    params = {'token':OAUTH_TOKEN,
              'channel':channel_id,
              'limit':limit}
    if options.oldest:
        timestamp = get_timestamp(options.oldest)
        params['oldest'] = timestamp
    if options.newest:
        timestamp = get_timestamp(options.newest)
        params['newest'] = timestamp
    r = requests.get(Conversations_History_API_URL, params=params)
    json_data = r.json()

    history = json_data['messages'][::-1]
    return history

def get_timestamp(s):
    JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
    return time.mktime(datetime.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=JST).timetuple())

def summarize(document, max=5, type=1):
    summarizer = LexRankSummarizer()
    if type == 2:
        summarizer = TextRankSummarizer()
    elif type == 3:
        summarizer = LsaSummarizer()

    #summarizer.stop_words = [" "]
    parser = PlaintextParser.from_string(document, Tokenizer("japanese"))
    summary = summarizer(document=parser.document, sentences_count=max)
    return summary

def get_texts(history):
    users = []
    texts = []
    times = []
    for message in history:
        if message['type'] == 'message' and  'subtype' not in message.keys() and 'bot_id' not in message.keys():
            users.append(message['user'])
            texts.append(message['text'])
            times.append(datetime.datetime.fromtimestamp(float(message['ts'])).strftime("%Y-%m-%d %H:%M"))
    return users, texts, times

def text2sentences(users, texts, times):
    sentences = []
    speakers = []
    source_id = []
    sentence_times = []
    for i in range(len(users)):
        for line in texts[i].splitlines():
            for sentence in re.split("．|。|？|！", line):
                sentence = sentence.strip()
                if len(sentence) > 0:
                    sentence += "。"
                    sentences.append(sentence)
                    speakers.append(users[i])
                    source_id.append(i)
                    sentence_times.append(times[i])
    return speakers, sentences, source_id, sentence_times


def show_sentences(summary, name, speakers, sentences, sentence_times):
    for sentence in summary:
        sentence = str(sentence)
        idx = sentences.index(sentence)
        print("○"+name[speakers[idx]], sentence_times[idx])
        print(sentence)
        print()
    
def show_whole_message(summary, texts, name, speakers, sentences, sources, times):
    covered = []
    for sentence in summary:
        # 同じのを繰り返す可能性あり
        sentence = str(sentence)
        idx = sentences.index(sentence)
        id = sources[idx]
        if id not in covered:
            print("○"+name[speakers[idx]], times[id])
            print(texts[id])
            print()
            covered.append(id)

def show_pinned_message(history, name):
    for message in history:
        if 'pinned_info' in message and message['type'] == 'message':
            print("○"+name[message['user']], datetime.datetime.fromtimestamp(float(message['ts'])).strftime("%Y-%m-%d %H:%M"))
            
            print(message['text'])
            print()

def show_reaction_message(history, tag, name):
    for message in history:
        if 'reactions' in message:
            for reaction in message['reactions']:
                if reaction['name'] == tag:
                    print("○"+name[message['user']], datetime.datetime.fromtimestamp(float(message['ts'])).strftime("%Y-%m-%d %H:%M"))
                    print(message['text'])
                    print()


def main(options):
    #print(options)
    if options.channel:
        channel_id = options.channel
    else:
        channel_id = DEFAULT_CHANNEL_ID
    
    history = get_history(channel_id, MAX, options)
    
    users, texts, times = get_texts(history)
    name = get_user_name_list(users)

    limit = 5
    if options.limit:
        limit = options.limit
        
    if options.pinned:
        show_pinned_message(history, name)
        sys.exit()
    elif options.reaction:
        show_reaction_message(history, options.reaction, name)
        sys.exit()
        
    speakers, sentences, sources, sentence_times = text2sentences(users, texts, times)
    document = "".join(sentences)
    summary = summarize(document, limit, options.type)
    
    if options.sentence:
        show_sentences(summary, name, speakers, sentences, sentence_times)
    else:
        show_whole_message(summary, texts, name, speakers, sentences, sources, times)
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Summarize Slack messages (Japanese only)')

    parser.add_argument('-t', '--type', type=int, help='select summarizer 1: LexRank, 2: TextRank, 3: LSA')
    parser.add_argument('-c', '--channel', help='set channel id')
    parser.add_argument('-l', '--limit', type=int, help='max lines for summarization')
    parser.add_argument('-o', '--oldest', help='set start date such as 2020-03-22 format')
    parser.add_argument('-n', '--newest', help='set last date such as 2020-04-17 format')
    parser.add_argument('-p', '--pinned', action='store_true', help='show pinned messages')
    parser.add_argument('-r', '--reaction', help='show messages with a specified reaction tag')    
    parser.add_argument('-s', '--sentence', action='store_true', help='only show important sentences')
    args = parser.parse_args()
    
    main(args)
