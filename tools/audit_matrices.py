"""Read-only O/N/W audit against one immutable Commons history prefix.

Defaults to a fictional world. An explicit --world may read a private saved game;
output contains aggregate counts and optional first-name comparisons only.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from commons_game import CommonsGame
from commons_game.engine import digest
from commons_game.expertise import matrix,cell
from commons_game.fullscreen import FullScreenTerminal
from commons_game.presentation import display_label,folded


def audit(game, *, at=None, source=None, pair=None):
    events=game.project('log',at=at)
    game=CommonsGame.from_log(events)  # Detached immutable prefix for every comparison.
    world=game.get_world();projection=matrix(world);n=len(projection['actors'])
    if source:
        capture=json.loads(Path(source).read_text())
        assert capture['expertise']==world['configuration']['ecosystem-expertise']['assertions']
    for i in range(n):
        for j in range(n):
            detail=cell(projection,i,j);lower=upper=0
            for a,b in zip(projection['O'][i],projection['N'][j]):
                lower+=int(a==b==1)
                upper+=int(a!=0 and b!=0)
            assert detail['value']==projection['W'][i][j]
            assert len(detail['matching_codes'])==lower==detail['lower']
            if projection['domains']:
                assert detail['upper']==upper
                assert detail['value']==(lower if lower==upper else None)
    result={'state_version':len(events),'world_digest':digest(world),'source_version':projection['source_version'],
        'source_capture_matches_saved_assertions':True if source else None,
        'actors':n,'domains':len(projection['domains']),'cells_checked':n*n,
        'offers':sum(v==1 for row in projection['O'] for v in row),
        'needs':sum(v==1 for row in projection['N'] for v in row),
        'offer_states':dict(Counter(v['offer']['state'] for v in projection['observations'].values())),
        'need_states':dict(Counter(v['need']['state'] for v in projection['observations'].values()))}
    if pair:
        indices=[]
        for name in pair:
            matches=[i for i,a in enumerate(projection['actors']) if folded(display_label(a))==folded(name)]
            if len(matches)!=1:
                choices=[display_label(a) for a in projection['actors'] if folded(name) in folded(display_label(a))]
                raise ValueError('Choose one unambiguous display name: '+', '.join(choices))
            indices.append(matches[0])
        i,j=indices;detail=cell(projection,i,j)
        ui=FullScreenTerminal(game,viewport=None,plain=True);ui.route.row,ui.route.column=i,j
        ui.matrix_screen();assert ui._matrix['W'][i][j]==detail['value']
        ui.handle('enter',ui.build_screen());ui.build_screen();assert ui._cell==detail
        result['pair']={'provider':display_label(detail['provider']),'requester':display_label(detail['requester']),
                        'heatmap':detail['value'],'inspector':ui._cell['value'],'confirmed_domains':len(detail['matching_codes']),
                        'lower':detail['lower'],'upper':detail['upper']}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world',type=Path);parser.add_argument('--at',type=int)
    parser.add_argument('--source',type=Path);parser.add_argument('--pair',nargs=2)
    args=parser.parse_args()
    if args.world:game=CommonsGame.load(args.world.expanduser())
    else:
        from playtest_matrix import fictional_world
        game=fictional_world()
    print(json.dumps(audit(game,at=args.at,source=args.source,pair=args.pair),indent=2))
