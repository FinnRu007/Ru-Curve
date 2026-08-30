"""Misst, wie lange Bot-Runden je Schwierigkeitsstufe dauern.

    python tools/bot_bench.py
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'
os.environ['RUCURVE_CONFIG']=os.path.join('tests','_tmp','config.json')
import pygame; pygame.init()
from rucurve.config import GameSettings
from rucurve.game.curve import Curve
from rucurve.game.world import World
from rucurve.game import bots
import statistics
s=GameSettings(countdown_seconds=0.0, arena_width=1267, arena_height=950)
for diff in (0.0,0.25,0.5,0.75,1.0):
    ts=[]
    for _ in range(6):
        cs=[Curve(i,f'B{i}',(9,9,9),is_bot=True,color_index=i) for i in range(4)]
        w=World(s,cs)
        for _ in range(60*45):
            for c in cs:
                if c.alive:
                    l,r,p=bots.control_bot(w,c,diff); w.set_input(c.id,l,r,p)
            w.step()
            if w.phase=='finished': break
        ts.append(w.time)
    print(f'Stufe {diff:4}: median {statistics.median(ts):5.1f}s  max {max(ts):5.1f}s', flush=True)
