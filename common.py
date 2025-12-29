import time
import requests
import jwt
import json
from json_repair import repair_json
from openai import OpenAI


def getPrompt(name):
    with open('prompts.txt','r',encoding='utf-8') as f:
        ptxt = f.read()
    plist = ptxt.split('::prompt')
    for p in plist:
        split = p.split('::content')
        title = split[0].strip()
        if title == name:
            return split[1].strip()
        

def getConfig(name):
    with open('config.json','r',encoding='utf-8') as f:
        content = json.load(f)
        return content.get(name)
           

class OpenAiClient:
    def __init__(self,ak=None,url=None,model=None):
        self.ak = ak 
        self.url = url
        self.model = model
        self.client = OpenAI(
            api_key=self.ak,
            base_url=self.url
        )

    def chat(self,messages):
        completion = self.client.chat.completions.create(
            model=self.model,  
            messages=messages
        )
        resMsg = completion.choices[0].message.content
        return resMsg


    def send(self,msg,isJson = True):
        messages = [
            {
                "role": "user",
                "content": msg
            }
        ]
        res = self.chat(messages)
        # print(res)
        if isJson:
            res = self.toJson(res)
        return res

    def toJson(self,txt):
        if '<json>' in txt:
            txt = txt.split('<json>')[1]
        if '</json>' in txt:
            txt = txt.split('</json>')[0]
        if '```json' in txt:
            txt = txt.split('```json')[1]
        if '```' in txt:
            txt = txt.split('```')[0]
        txt = repair_json(txt,ensure_ascii=False)
        return txt
        

