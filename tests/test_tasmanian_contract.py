"""Tasmanian Owner scope and orb continuity; pixel hashes do not certify natural gait."""
from pathlib import Path
import hashlib,json,unittest
from PIL import Image
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads((R/p).read_text())
class TasmanianContract(unittest.TestCase):
 def test_exact_owner_action_scope_and_size(self):
  m=read('assets/tasmanian_king_crab/clips/animation-clips.json');meta=read('assets/tasmanian_king_crab/godot_bundle/engine-export.json')
  self.assertEqual(meta['render_contract']['body_clips'],['idle','walk','attack_nomal','power_up','hit','ko'])
  self.assertEqual(set(m['clips']),set(meta['render_contract']['body_clips']+meta['render_contract']['effect_clips']))
  for excluded in ['jump','run','attack_heavy','aura_loop','guard','win']:self.assertNotIn(excluded,m['clips'])
  live=Image.open(R/'assets/tasmanian_king_crab/clips/frames/frame-00.png').convert('RGBA')
  master=Image.open(R/'work/characters/tasmanian_king_crab/size-master/master.png').convert('RGBA');self.assertEqual(live.tobytes(),master.tobytes());self.assertEqual(live.size,(384,256))
  b=live.getchannel('A').getbbox();self.assertEqual((b[2]-b[0],b[3]-b[1]),(133,64))
 def test_source_six_plus_two_bridges_and_release_from_peak(self):
  m=read('assets/tasmanian_king_crab/clips/animation-clips.json');loop=m['clips']['power_orb_loop'];proj=m['clips']['power_orb_projectile']
  self.assertEqual(len(loop['frames']),8);self.assertTrue(loop['loop']);self.assertFalse(proj['loop']);self.assertEqual(proj['frames'],[loop['frames'][i] for i in [5,6,7,0]])
  self.assertEqual(sum(m['clips']['power_up']['ticks'][:2]),24)
  evidence=read('work/characters/tasmanian_king_crab/atlas-v1/fx-source-evidence.json');self.assertEqual([x['newly_generated'] for x in evidence],[False]*6+[True]*2)
  self.assertEqual([x['source_center_px'][0] for x in evidence[:6]],sorted([x['source_center_px'][0] for x in evidence[:6]],reverse=True))
  hashes=[m['frames'][i]['source']['file_sha256'] for i in loop['frames']];self.assertEqual(len(set(hashes)),8)
 def test_walk_is_forward_unique_cycle_and_body_alpha_is_hard(self):
  m=read('assets/tasmanian_king_crab/clips/animation-clips.json');walk=m['clips']['walk'];self.assertEqual(walk['loop_policy'],'cycle');self.assertEqual(len(walk['frames']),8)
  self.assertEqual(len({m['frames'][i]['source']['file_sha256'] for i in walk['frames']}),8)
  for name in ['idle','walk','attack_nomal','power_up','hit','ko']:
   for i in m['clips'][name]['frames']:
    im=Image.open(R/'assets/tasmanian_king_crab/clips'/m['frames'][i]['file']);h=im.getchannel('A').histogram();self.assertEqual(sum(h[1:255]),0,(name,i))

 def test_horizontal_flip_without_turn_contract(self):
  import hashlib
  roster=read('assets/roster.json')
  crab=next(c for c in roster['characters'] if c['character_id']=='tasmanian_king_crab')
  meta=read('assets/tasmanian_king_crab/godot_bundle/engine-export.json')
  fc=crab['facing_contract']
  self.assertEqual(fc['default_spawn_facing'],'right')
  self.assertEqual(fc['supported_spawn_facings'],['right','left'])
  loc=meta['render_contract']['locomotion']
  self.assertEqual(loc,crab['render_contract']['locomotion'])
  self.assertFalse(loc['sideways_strafe'])
  self.assertFalse(loc['lock_spawn_facing'])
  self.assertEqual(loc['default_spawn_facing'],'right')
  self.assertTrue(loc['allow_turn_or_flip'])
  self.assertEqual(loc['reverse_playback_mode'],'forward_cycle')
  self.assertTrue(loc['patrol']['enabled'])
  self.assertEqual(loc['default_scale'],1.25)
  self.assertEqual(loc['screen_speed_px_per_second'],115)
  self.assertEqual(meta['render_contract']['turning']['clip'],None)
  self.assertEqual(meta['render_contract']['turning']['method'],'instant_flip')
  self.assertEqual(meta['render_contract']['turning']['turn_speed_multiplier'],1.3)
  self.assertNotIn('turn',meta['clips'])
  approval=read('work/characters/tasmanian_king_crab/step2-visual-fix/snapshot-before/owner_approval.json')
  snap=R/'work/characters/tasmanian_king_crab/step2-visual-fix/snapshot-before'
  self.assertEqual(hashlib.sha256((snap/'tasmanian_king_crab-atlas-00.png').read_bytes()).hexdigest(),approval['atlas_sha256'])
  self.assertEqual(hashlib.sha256((snap/'tasmanian_king_crab.tres').read_bytes()).hexdigest(),approval['tres_sha256'])
  self.assertEqual(hashlib.sha256((R/'scenes/TasmanianKingCrab.tscn').read_bytes()).hexdigest(),approval['prefab_sha256'])
  roster_entry=next(c for c in read('assets/roster.json')['characters'] if c['character_id']=='tasmanian_king_crab')
  self.assertEqual(roster_entry['status'],'finalized_pending_owner_reapproval')
  self.assertEqual(roster_entry['motion_quality']['status'],'reviewed_pending_owner')
  self.assertFalse(roster_entry['motion_quality']['owner_approved'])
  self.assertEqual(roster_entry['motion_quality']['previous_revision_atlas_sha256'],approval['atlas_sha256'])
  from PIL import Image
  clips_m=read('assets/tasmanian_king_crab/clips/animation-clips.json')
  idle_lums=[]
  for cname in ('idle','walk'):
   for fi in clips_m['clips'][cname]['frames']:
    im=Image.open(R/'assets/tasmanian_king_crab/clips'/clips_m['frames'][fi]['file']).convert('RGBA')
    bb=im.getbbox();self.assertIsNotNone(bb);self.assertEqual(bb[3],224,(cname,fi))
    if cname=='idle':
     px=[r*0.299+g*0.587+b*0.114 for (r,g,b,a) in im.get_flattened_data() if a>0]
     idle_lums.append(sum(px)/len(px))
  self.assertLessEqual(max(idle_lums)-min(idle_lums),2.5)
