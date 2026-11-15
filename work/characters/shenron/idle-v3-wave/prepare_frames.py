#!/usr/bin/env python3
"""Whole-pose keying; same reference grid and shared master palette, no body rigging."""
from pathlib import Path
import importlib.util,json,shutil
from PIL import Image
BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('extractor',BASE/'extract_wave_frame.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ref={k:getattr(m,k) for k in ['REF_X0','REF_Y0','REF_W','REF_H']}
master=Image.open(BASE.parent/'master-v1/master.png').convert('RGBA')
canvas=Image.new('RGBA',(384,272),(0,0,0,0));canvas.paste(master,(0,0));canvas.save(BASE/'idle_00.png')
for i in range(1,8):
 raw=BASE/f'raw/idle_{i:02d}-raw.png';width,height=Image.open(raw).size
 if width!=height:raise ValueError('Expected square source image')
 for k,v in ref.items():setattr(m,k,v*width/1024)
 im=m.extract_keyframe(raw,dy_px=0);im.save(BASE/f'idle_{i:02d}.png');print(i,im.getbbox())
manifest={'schema':'generate2dsprite.animation_clips.v2','frames':[f'idle_{i:02d}.png' for i in range(8)],'anchor_px':[192,240],'clips':{'idle':{'frames':list(range(8)),'ticks':[12]*8,'loop_policy':'cycle'}},'states':{'idle':'idle'},'sampling':'nearest','pixel_art':True,'art_source':'host_image','body_height_px':201}
(BASE/'clips-input.json').write_text(json.dumps(manifest,indent=2)+'\n')
