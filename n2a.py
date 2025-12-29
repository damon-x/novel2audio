from common import *
import uuid
import os
import dashscope



class NovelParser:
    def __init__(self,client):
        self.client = client
        self.chunk_size = 1000
        self.sentence_length = 100
    def split_text(self,txt):
        res = []
        s1 = txt.split("\n")
        batch = ""
        for s in s1:
            if len(batch) + len(s) <= self.chunk_size:
                batch = batch +"\n" + s
            else:
                res.append(batch)
                batch = s
        res.append(batch)
        return res 

    # 首次提取
    def first_select(self,sl,file):
        ptpl = getPrompt("selectCharacter")
        characterName = []
        characterList = []
        with open(file, "w", encoding="utf-8") as f:
            pass
        for i,x in enumerate(sl):
            p = ptpl.replace("{chunk}",x)
            p = p.replace("{character}",json.dumps(characterList,indent=2,ensure_ascii=False))
            res = self.client.send(p)
            resObj = json.loads(res)
            print(f"{i}/{len(sl)}")
            if len(resObj) == 0:
                print(f"find 0 {i}")
            with open(file,'a') as f:
                chunkRes = {}
                chunkRes["idx"] = i
                chunkRes["res"] = resObj
                f.write(json.dumps(chunkRes,ensure_ascii=False,indent=2))
                f.write("\n=====")
                for chat in resObj:
                    character = chat.get("character")
                    if character not in characterName and "角色" not in character:
                        characterName.append(characterName)
                        characterList.append({"character":chat.get("character"),"sex":chat.get("sex"),"ageGroup":chat.get("ageGroup")})
                    elif character in characterName:
                        for c in characterList:
                            if c['character'] == chat.get("character") and  ( c['sex'] == "未知" or not c['sex']):
                                c['sex'] = chat.get("sex")

    # 查找需要重新确认的对话
    def chek_need_insures(self,file):
        needInsures = {}
        characters = {}
        with open(file,'r') as f:
            ca = f.read()
            for x in ca.split("====="):
                if not x.strip():
                    continue
                e = json.loads(x)
                if e.get("res"):
                    for chat in e.get("res"):
                        character = chat.get("character")
                        if "角色" in character:
                            if e.get("idx") not in needInsures:
                                needInsures[e.get("idx")] = []
                            needInsures[e.get("idx")].append(chat)
                        elif character not in characters:
                            characters[character] = chat
                        elif character in characters and ( characters[character]['sex'] == "未知" or not characters[character]['sex']  ):
                            characters[character]['sex'] == chat.get("sex")
        character_list = [{"character":characters[x]["character"],"sex":characters[x]["sex"]} for x in characters]
        return needInsures,character_list

    # 二次提取
    def second_select(self,sl,needInsures,character_list,res_file):
        with open(res_file, "w", encoding="utf-8") as f:
            pass
        ensureRes = {}
        characterName = [x['character'] for x in character_list]
        print(character_list)
        for e in needInsures:
            print(e,end=",")
        for e in needInsures:
            print(e)
            print(character_list)
            x = needInsures[e]
            content = sl[e-1] +"\n"+  sl[e]
            textList = [i.get("text") for i in x]
            ptpl = getPrompt("ensureCharacter")
            p = ptpl.replace("{text}",json.dumps(textList,ensure_ascii=False,indent=2))
            p = p.replace("{characterList}",json.dumps(character_list,ensure_ascii=False,indent=2))
            p = p.replace("{content}",content)
            aiRes = self.client.send(p)
            resObj = json.loads(aiRes)
            for chat in resObj:
                character = chat.get("character")
                if character not in characterName and "角色" not in character:
                    characterName.append(character)
                    character_list.append({"character":chat.get("character"),"sex":chat.get("sex")})
                elif character in characterName:
                    for c in character_list:
                        if c['character'] == chat.get("character") and  ( c['sex'] == "未知" or not c['sex']):
                            c['sex'] = chat.get("sex")
            ensureRes[e] = resObj
        
        with open(res_file , 'a') as f:
            f.write(json.dumps(ensureRes,ensure_ascii=False,indent=2))
        return ensureRes

    # 补齐信息
    def fix_character(self,f1_file,ensureRes):
        finalResult = {}
        with open(f1_file,'r') as f:
            ca = f.read()
            for x in ca.split("====="):
                if not x.strip():
                    continue
                e = json.loads(x)
                if e.get("idx") not in finalResult:
                    finalResult[e.get("idx")] = []
                chatList = finalResult[e.get("idx")] 
                if e.get("res"):
                    nocidx = 0
                    for chat in e.get("res"):
                        character = chat.get("character")
                        if "角色" not in character:
                            chatList.append(chat)
                        else:
                            chat['character'] = ensureRes[(e.get("idx"))][nocidx]['character']
                            chat['sex'] = ensureRes[(e.get("idx"))][nocidx]['sex']
                            chat['ageGroup'] = ensureRes[(e.get("idx"))][nocidx]['ageGroup']
                            # if  chat['sex'] == "未知" and characterInfo.get(chat['character']):
                            #     chat['sex'] = characterInfo.get(chat['character'])
                            nocidx = nocidx + 1
                            print(chat)
                            chatList.append(chat)
            return finalResult
    def mergeCharacter(self,characterList , finalResult):
        ptpl = getPrompt("mergeCharacter")
        p = ptpl.replace("{characterList}",json.dumps(characterList,ensure_ascii=False,indent=2))
        aiRes = self.client.send(p)
        resObj = json.loads(aiRes)
        name_map = {}
        
        for k in resObj:
            v = resObj[k]
            if len(v) > 1:
                for name in v:
                    name_map[name]=k
        if len(name_map) > 1:
            for idx in finalResult:
                chatList = finalResult[idx]
                for chat in chatList:
                    if chat['character'] in name_map:
                        chat['character']  = name_map[chat['character']]
        return finalResult

    def gen_script(self,sl, finalResult):
        final_sentences = []
        for sli in range(len(sl)):
            chunk = sl[sli]
            paragraph = []
            c_res = finalResult[sli]
            for i in range(len(c_res)):
                if c_res[i]['text'] not in chunk:
                    print(f"error {sli} - {i} - {finalResult[sli][i]}")
                    continue
                paragraph.append({"content":chunk.split(c_res[i]['text'])[0],"character":"旁白","sex":'',"ageGroup":'',"tone":''})
                paragraph.append({"content":c_res[i]['text'],"character":c_res[i]['character'],"sex":c_res[i]["sex"],"ageGroup":c_res[i]['ageGroup'],"tone":c_res[i]['tone']})
                chunk = c_res[i]['text'].join(chunk.split(c_res[i]['text'])[1:])
            if chunk.strip():
                paragraph.append({"content":chunk,"character":"旁白","sex":'',"ageGroup":'',"tone":''})
            sentences = []
            for p in paragraph:
                if len(p['content']) < self.sentence_length:
                    sentences.append(p)
                else:
                    for s in p['content'].split("。"):
                        sentences.append({"content":s,"character":p['character'],"sex":p["sex"],"ageGroup":p['ageGroup'],"tone":p['tone']})
            final_sentences.extend(sentences)
        return final_sentences

    def parser(self,file_path):
        with open(file_path,'r') as f:
            content = f.read()
        chunks = self.split_text(content)
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        first_res_file_path = file_name+"_first_res_" + str(uuid.uuid4()).replace("-","")+".txt"
        second_res_file_path =file_name+"_second_res_" + str(uuid.uuid4()).replace("-","")+".txt"
        self.first_select(chunks,first_res_file_path)
        needInsures,character_list = self.chek_need_insures(first_res_file_path)
        ensureRes = self.second_select(chunks, needInsures,character_list,second_res_file_path)
        finalResult = self.fix_character(first_res_file_path,ensureRes)
        self.mergeCharacter(character_list , finalResult)
        final_sentences = self.gen_script(chunks, finalResult)

        final_sentences_file_path =file_name+"_final_sentences_" + str(uuid.uuid4()).replace("-","")+".txt"
        with open(final_sentences_file_path,'w') as f:
            f.write(json.dumps(final_sentences,ensure_ascii=False,indent=2))
        return final_sentences







class AudioGenerate:
    def __init__(self,txt_client , tts_model_sk):
        self.voice_type_list = getConfig("voice_type_list")
        self.txt_client = txt_client
        self.tts_model_sk = tts_model_sk
    
    def get_speckers(self,sentences):
        speakers = []
        for st in sentences:
            speaker = f"{st['character']}-{st["sex"]}-{st['ageGroup']}"
            if speaker not in speakers:
                speakers.append(speaker)
        return speakers

    def gen_voice_type(self,speakers):
        ptpl = getPrompt("chooseVoice")
        p = ptpl.replace("{speakerList}",json.dumps(speakers,ensure_ascii=False,indent=2))
        p = p.replace("{voiceList}",json.dumps(self.voice_type_list,ensure_ascii=False,indent=2))
        # print(p)
        ai_res = self.txt_client.send(p)
        res_obj = json.loads(ai_res)
        return res_obj

    
        
    def gen_single_voice(self,text,voice_type):
        print(text,voice_type)
        dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
        response = dashscope.MultiModalConversation.call(
            model="qwen3-tts-flash-2025-11-27",
            api_key=self.tts_model_sk,
            text=text,
            voice=voice_type,
            language_type="Chinese", 
            stream=False
        ) 
        print(response)
        return response.output.audio.url
        
    def download_wav_audio(self,url, save_path):
        try:
            # 发送 GET 请求获取音频流（stream=True 避免一次性加载大文件）
            response = requests.get(url, stream=True, timeout=30)
            # 验证请求是否成功（状态码 200 表示正常）
            response.raise_for_status()
            
            # 以二进制写入模式保存文件
            with open(save_path, 'wb') as file:
                # 分块下载（每块 1024 字节），适合大文件
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:  # 过滤空块
                        file.write(chunk)
            
            print(f"音频下载成功！已保存为：{save_path}")
        except requests.exceptions.RequestException as e:
            print(f"下载失败：{str(e)}")
            print("可能原因：URL 已过期、网络异常、文件不存在")
    
    def gen_voice(self,res_path , voice_map,final_sentences):
        cnt = 0
        for i,x in enumerate(final_sentences):
            if x['character'] == '旁白' or not x['content'].strip():
                continue
            else:
                speaker = f"{x['character']}-{x["sex"]}-{x['ageGroup']}"
                file_path = f"{res_path}/{i}.wav"
                if os.path.exists(file_path):
                    continue
                audio_url = self.gen_single_voice(x['content'],voice_map[speaker])
                self.download_wav_audio(audio_url,file_path)

    def generate(self,sentences,output_path):
        speakers = self.get_speckers(sentences)
        voice_map = self.gen_voice_type(speakers)
        # print(voice_map)
        self.gen_voice(output_path,voice_map,sentences)
                


class Novel2Audio:
    def __init__(self, api_key,url , text_model,file_path,output_dir_path):
        self.api_key = api_key
        self.text_model = text_model if text_model else "qwen3-max"
        self.url = url if url else "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.client = OpenAiClient(ak=api_key,url=self.url, model = text_model)
        
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"文件不存在：{file_path}")
        if not os.path.isdir(output_dir_path):
            print(f"错误：路径 {output_dir_path} 不是有效目录，即将递归创建目录")
            if os.path.isfile(output_dir_path):
                raise FileNotFoundError(f"{file_path} 需要是目录")
            os.makedirs(output_dir_path, exist_ok=True)
            print(f"目录创建成功：{output_dir_path}")

        

        self.output_dir_path = output_dir_path
        self.file_path  = file_path 

    def generate(self):
        novel_parser = NovelParser(self.client)
        final_sentences = novel_parser.parser(self.file_path )

        audio_generate =  AudioGenerate(self.client,self.api_key)
        audio_generate.generate(final_sentences,self.output_dir_path)

    
        


# 替换参数
n2a = Novel2Audio("api-key",
                  "https://dashscope.aliyuncs.com/compatible-mode/v1" , 
                  "qwen3-max",
                    "围城.txt" ,
                    "./tmpaudio")

n2a.generate()

