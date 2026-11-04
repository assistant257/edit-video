"""Render a natural-speed Vietnamese captioned review; no source committed."""
import argparse,json,subprocess,re
from pathlib import Path

def run(args):
    return subprocess.run([str(x) for x in args],check=True,capture_output=True,text=True)

def stamp(t,srt=False):
    units=1000 if srt else 100
    n=round(max(0,t)*units);s,f=divmod(n,units);m,s=divmod(s,60);h,m=divmod(m,60)
    return f'{h:02}:{m:02}:{s:02},{f:03}' if srt else f'{h}:{m:02}:{s:02}.{f:02}'

def clean(t):
    return re.sub(r'[{}\\\r\n]',' ',t).strip()

def make_cues(words):
    cues=[];group=[]
    for w in words:
        text=' '.join(x['word'].strip() for x in group+[w])
        gap=bool(group) and w['start']-group[-1]['end']>.6
        if group and (gap or len(text)>44 or (w['end']-group[0]['start']>3.2 and len(group)>=3)):
            cues.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(x['word'].strip() for x in group)})
            group=[]
        group.append(w)
    if group:cues.append({'start':group[0]['start'],'end':group[-1]['end'],'text':' '.join(x['word'].strip() for x in group)})
    return cues

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--model',default='small');a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    meta=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',a.source]).stdout)
    v=next(x for x in meta['streams'] if x['codec_type']=='video')
    if not any(x['codec_type']=='audio' for x in meta['streams']):raise ValueError('Source has no audio stream')
    duration=float(meta['format']['duration'])
    if not 0<duration<=1800:raise ValueError('Review runner supports up to 30 minutes')
    run(['ffmpeg','-nostdin','-y','-v','error','-i',a.source,'-map','0:a:0','-ac','1','-ar','16000',a.output/'speech.wav'])
    import wave
    import numpy as np
    with wave.open(str(a.output/'speech.wav'),'rb') as wav:
        assert wav.getnchannels()==1 and wav.getsampwidth()==2 and wav.getframerate()==16000
        speech=np.frombuffer(wav.readframes(wav.getnframes()),dtype=np.int16).astype(np.float32)/32768.0
    print(f'Source duration: {duration:.3f}s; source canvas: {v["width"]}x{v["height"]}',flush=True)
    from faster_whisper import WhisperModel
    model=WhisperModel(a.model,device='cpu',compute_type='int8',cpu_threads=4)
    segs,info=model.transcribe(speech,language='vi',word_timestamps=True,vad_filter=True,beam_size=5,condition_on_previous_text=False)
    words=[];segments=[]
    for s in segs:
        segments.append({'start':s.start,'end':s.end,'text':s.text,'avg_logprob':s.avg_logprob})
        for w in s.words or []:
            if w.end>w.start:words.append({'word':re.sub(r'(?i)\bKBI\b','KPI',w.word),'start':w.start,'end':w.end,'probability':w.probability})
    if not words:raise ValueError('No speech recognized; do not emit fabricated captions')
    print(f'Recognized {len(words)} words in {len(segments)} segments',flush=True)
    cues=make_cues(words)
    (a.output/'transcript.json').write_text(json.dumps({'language':info.language,'segments':segments,'words':words},ensure_ascii=False,indent=2))
    (a.output/'captions.srt').write_text('\n\n'.join(f'{i}\n{stamp(c["start"],True)} --> {stamp(c["end"],True)}\n{c["text"]}' for i,c in enumerate(cues,1))+'\n')
    # Match source display orientation, do not center-crop evidence or stretch people.
    rotation=next((int(d.get('rotation',0)) for d in v.get('side_data_list',[]) if 'rotation' in d),0)
    w,h=int(v['width']),int(v['height'])
    if abs(rotation)%180==90:w,h=h,w
    factor=min(1,1920/max(w,h));w=int(w*factor)//2*2;h=int(h*factor)//2*2
    fs=round(w*.065);margin=round(h*.26);side=round(w*.14)
    header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans,{fs},&H00FFFFFF,&H00FFFFFF,&H00282820,&H80202020,-1,0,0,0,100,100,0,0,1,2,1,2,{side},{side},{margin},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    (a.output/'captions.ass').write_text(header+'\n'.join(f'Dialogue: 0,{stamp(c["start"])},{stamp(c["end"])},Default,,0,0,0,,{clean(c["text"])}' for c in cues)+'\n')
    # Work in output dir so filter paths contain no shell or ASS escapes.
    dest=a.output/'review.mp4'
    subprocess.run(['ffmpeg','-nostdin','-y','-v','warning','-i',str(a.source.resolve()),'-map','0:v:0','-map','0:a:0','-vf',f'scale={w}:{h},setsar=1,ass=captions.ass','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-ar','48000','-movflags','+faststart',str(dest.resolve())],cwd=a.output,check=True)
    run(['ffmpeg','-v','error','-i',dest,'-f','null','-'])
    run(['ffmpeg','-y','-v','error','-i',dest,'-vf',f'fps=1/{max(1,duration/12)},scale=240:-1,tile=4x3','-frames:v','1',a.output/'contact-sheet.jpg'])
    final=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',dest]).stdout)
    if abs(float(final['format']['duration'])-duration)>.5:raise ValueError('Duration mismatch')
    flags=[{'start':c['start'],'end':c['end'],'text':c['text']} for c in cues if len(c['text'])/max(.01,c['end']-c['start'])>22]
    (a.output/'review-notes.json').write_text(json.dumps({'source_duration':duration,'output_duration':final['format']['duration'],'speed':1,'content_cuts':False,'caption_review':'automatic ASR, human spelling and timing review pending','listening_review':'not_performed','frame_review':'pending','fast_cues':flags,'low_confidence_words':[w for w in words if w['probability']<.65]},ensure_ascii=False,indent=2))
    (a.output/'source-metadata.json').write_text(json.dumps(meta,indent=2))
    (a.output/'speech.wav').unlink()
    print('MP4 and subtitle files rendered; human audiovisual review still required.')
if __name__=='__main__':main()
