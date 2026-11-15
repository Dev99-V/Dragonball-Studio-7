#!/usr/bin/env python3
from pathlib import Path
import json,subprocess
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage
BASE=Path(__file__).resolve().parent;OUT=BASE/'evidence';OUT.mkdir(exist_ok=True)
frames=[BASE/f'idle_{i:02d}.png' for i in range(8)]
master=np.array(Image.open(BASE.parent/'master-v1/master.png').convert('RGBA'));palette=set(map(tuple,master[master[:,:,3]>0,:3]))
records=[];arrays=[]
for i,path in enumerate(frames):
 a=np.array(Image.open(path).convert('RGBA'));arrays.append(a);mask=a[:,:,3]>0
 key=mask&(a[:,:,2]>75)&((a[:,:,2].astype(int)-np.maximum(a[:,:,0],a[:,:,1]).astype(int))>25);rim=mask&~ndimage.binary_erosion(mask)
 eyes=[]
 for x0,x1 in [(165,181),(181,195)]:
  roi=a[65:83,x0:x1];red=(roi[:,:,0].astype(int)>roi[:,:,1].astype(int)+55)&(roi[:,:,0].astype(int)>roi[:,:,2].astype(int)+40)&(roi[:,:,3]>0);yy,xx=np.where(red)
  eyes.append({'red_pixels':int(red.sum()),'bbox':[int(xx.min()+x0),int(yy.min()+65),int(xx.max()-xx.min()+1),int(yy.max()-yy.min()+1)] if len(xx) else None})
 metrics=json.loads(subprocess.check_output(['python3','tools/art/measure_pixel_sharpness.py',str(path)]));metrics.update(frame=i,opaque_key_px=int(key.sum()),enclosed_key_pockets=int(ndimage.label(key)[1]),outer_ring_spill_fraction=float((key&rim).sum()/max(1,rim.sum())),master_palette_subset=set(map(tuple,a[mask,:3])).issubset(palette),eyes=eyes);records.append(metrics)
heat=Image.new('RGB',(384*4,286*2),(20,20,20));draw=ImageDraw.Draw(heat);steps=[]
for i,a in enumerate(arrays):
 b=arrays[(i+1)%8];delta=np.abs(a.astype(int)-b.astype(int));strength=np.clip(delta.max(axis=2)*3,0,255).astype('uint8');rgb=np.zeros((256,384,3),dtype='uint8');rgb[:,:,0]=strength;rgb[:,:,1]=strength//3;xx=(i%4)*384;yy=(i//4)*286;heat.paste(Image.fromarray(rgb),(xx,yy+30));draw.text((xx+8,yy+8),f'{i} -> {(i+1)%8}',fill='white');steps.append({'from':i,'to':(i+1)%8,'rgba_mae':float(delta.mean()),'changed_pixels':int(np.any(a!=b,axis=2).sum())})
heat.save(OUT/'consecutive-diff.png');(OUT/'frame-measurements.json').write_text(json.dumps({'frames':records,'adjacent_transitions':steps},indent=2)+'\n');print(json.dumps([{'frame':r['frame'],'bbox':r['body_bbox_px'],'sobel':r['edge_acutance_sobel'],'eyes':r['eyes']} for r in records],indent=2))
