#!/usr/bin/env python3
"""Key complete generated inbetween poses; preserve original even-position PNGs."""
from pathlib import Path
import importlib.util
from PIL import Image
import json,shutil
BASE=Path(__file__).resolve().parent
OLD=BASE.parent/'idle-v1'
spec=importlib.util.spec_from_file_location('extractor',OLD/'extract_shenron_frame.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ref={k:getattr(m,k) for k in ['REF_X0','REF_Y0','REF_W','REF_H']}
original=[BASE.parent/'master-v1/master.png',OLD/'idle_01-candidate.png',OLD/'idle_02-host-candidate.png',OLD/'idle_03-host-candidate.png']
for i,f in enumerate(original):shutil.copy2(f,BASE/f'idle_{i*2:02d}.png')
for i,dy in [(1,0),(3,-1),(5,-2),(7,0)]:
 raw=BASE/f'raw/idle_{i:02d}-raw.png'
 width,height=Image.open(raw).size
 assert width==height
 for k,v in ref.items():setattr(m,k,v*width/1024)
 im=m.extract_keyframe(raw,dy_px=dy)
 target=BASE/f'idle_{i:02d}.png';im.save(target);print(target.name,im.getbbox())
manifest={'schema':'generate2dsprite.animation_clips.v2','frames':[f'idle_{i:02d}.png' for i in range(8)],'anchor_px':[192,240],'clips':{'idle':{'frames':list(range(8)),'ticks':[6]*8,'loop_policy':'cycle'}},'states':{'idle':'idle'},'sampling':'nearest','pixel_art':True,'art_source':'host_image','body_height_px':201}
(BASE/'clips-input.json').write_text(json.dumps(manifest,indent=2)+'\n')
