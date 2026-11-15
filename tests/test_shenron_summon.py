import hashlib
import json
from pathlib import Path
import unittest
import numpy as np
from PIL import Image, ImageFilter
from tools.preview import server
ROOT=Path(__file__).resolve().parents[1]
class ShenronSummonAssets(unittest.TestCase):
    def test_seven_numbered_native_crops_and_shared_atlas(self):
        c=server.load_rituals()['shenron_summon']
        self.assertEqual([i['number'] for i in c['items']], list(range(1,8)))
        self.assertEqual(c['qa']['star_counts'],list(range(1,8)))
        atlas=Image.open(ROOT/c['atlas']).convert('RGBA')
        evidence=json.loads((ROOT/'work/rituals/shenron_summon/v2-flash-hover/evidence/extraction.json').read_text())
        source=Image.open(ROOT/c['source_images'][0]['file']).convert('RGB')
        for item in c['items']:
            im=Image.open(ROOT/item['file']).convert('RGBA')
            x,y,w,h=item['region']
            self.assertEqual(im.tobytes(),atlas.crop((x,y,x+w,y+h)).tobytes())
            self.assertEqual(im.getpixel((0,0))[3],0)
            record=evidence['items']['ball_'+str(item['number'])]
            original=np.array(source.crop(record['source_box_xyxy']))
            mask=np.array(im.getchannel('A').filter(ImageFilter.MinFilter(5)))==255
            self.assertTrue(np.array_equal(np.array(im)[:,:,:3][mask],original[mask]),'Opaque source interior changed')
            self.assertEqual(record['star_count'],item['number'])
            self.assertEqual(len(record['star_component_areas']),item['number'])
        self.assertEqual(hashlib.sha256((ROOT/c['atlas']).read_bytes()).hexdigest(),c['atlas_sha256'])

    def test_shared_six_second_contract_and_ground_source(self):
        c=server.load_rituals()['shenron_summon'];t=c['timeline'];l=c['layout']
        self.assertEqual(c['tick_hz'],60)
        self.assertEqual(t['ready_tick'],360)
        self.assertEqual(6*t['launch_stride_ticks']+t['flight_ticks'],t['last_arrival_tick'])
        self.assertLess(t['last_arrival_tick'],t['vanish_start_tick'])
        self.assertLess(t['vanish_start_tick'],t['ground_start_tick'])
        self.assertLess(t['ground_start_tick'],t['dragon_start_tick'])
        self.assertEqual(l['map_center_px'],[960,540]);self.assertEqual(l['ground_y'],840)
        self.assertEqual(l['ground_display_width_px'],144);self.assertEqual(l['dragon_scale'],2.76)
        self.assertEqual(c['behavior']['trigger'],'button_only')
        self.assertTrue(c['behavior']['persist_until_dismissed'])
        for source in c['source_images']:
            self.assertEqual(hashlib.sha256((ROOT/source['file']).read_bytes()).hexdigest(),source['sha256'])
        with __import__('zipfile').ZipFile(__import__('io').BytesIO(server.build_godot_zip_bytes())) as archive:
            names = set(archive.namelist())
            self.assertIn('assets/rituals/shenron_summon/sequence.json', names)
            self.assertIn('assets/rituals/shenron_summon/dissolve-threshold.png', names)
            self.assertIn('scenes/ShenronSummon2D.gd', names)
            self.assertIn('scenes/ShenronPixelDissolve.gdshader', names)

    def test_ground_native_pixel_finish_and_flight_preservation(self):
        c=server.load_rituals()['shenron_summon']
        im=Image.open(ROOT/'assets/rituals/shenron_summon/ground-cluster.png').convert('RGBA')
        self.assertEqual(im.size,(144,136))
        self.assertEqual(sum(im.getchannel('A').histogram()[1:255]),0)
        previous=json.loads((ROOT/'work/rituals/shenron_summon/v2-flash-hover/snapshot-before/sequence.json').read_text())
        for key in ['launch_stride_ticks','flight_ticks','last_arrival_tick','vanish_start_tick']:
            self.assertEqual(c['timeline'][key],previous['timeline'][key])
        for a,b in zip(c['items'],previous['items']):
            self.assertEqual(a['formation_offset_px'],b['formation_offset_px'])
            self.assertEqual((ROOT/a['file']).read_bytes(),(ROOT/'work/rituals/shenron_summon/v2-flash-hover/snapshot-before/items'/Path(a['file']).name).read_bytes())

    def test_pixel_dissolve_mask_and_unchanged_approved_combo(self):
        c=server.load_rituals()['shenron_summon'];r=c['reveal']
        self.assertEqual(r['method'],'pixel_dissolve')
        self.assertEqual(r['cell_size_canvas_px'],4)
        im=Image.open(ROOT/r['mask']).convert('RGBA')
        self.assertEqual(im.size,(96,68))
        self.assertEqual(hashlib.sha256((ROOT/r['mask']).read_bytes()).hexdigest(),r['mask_sha256'])
        values=np.array(im)[:,:,0]
        self.assertEqual(len(np.unique(values)),256)
        counts=[int(((values+0.5)/256<=p).sum()) for p in [0,.25,.5,.75,1]]
        self.assertEqual(counts[0],0);self.assertEqual(counts[-1],96*68)
        self.assertTrue(all(a<b for a,b in zip(counts,counts[1:])))
        old=json.loads((ROOT/'work/rituals/shenron_summon/v3-pixel-dissolve/snapshot-before/sequence.json').read_text())
        for key in ['timeline','layout','items','regions','atlas_sha256']:
            self.assertEqual(c[key],old[key])
