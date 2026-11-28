"""C31/C33 offline CLI. Run with PYTHONPATH=api;pipeline from repository root."""

import argparse
import json
from pathlib import Path
from time import monotonic

from src.evaluation.recommendation import (create_pool, evaluate, freeze, read_cases, validate_labels)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    pool=commands.add_parser('pool',help='Create new top20 bundle and blinded sheets; no metrics')
    pool.add_argument('--snapshot',type=Path,required=True)
    pool.add_argument('--cases',type=Path,required=True)
    pool.add_argument('--output-dir',type=Path,required=True)
    revision=commands.add_parser('revise-scenarios',help='Revise intent/guidance only, retain ranking/pool/sample bytes')
    for flag in ('run','cases','output-dir'):revision.add_argument('--'+flag,type=Path,required=True)
    revision.add_argument('--label-file',type=Path,action='append',default=[])
    export=commands.add_parser('review-export',help='Verify fixed pool and export new blinded review package')
    export.add_argument('--run',type=Path,required=True)
    export.add_argument('--snapshot',type=Path,required=True)
    export.add_argument('--output-dir',type=Path,required=True)
    imp=commands.add_parser('review-import',help='Validate an edited exchange CSV; save draft or explicitly finalize')
    for flag in ('run','bundle','input','output-dir'):imp.add_argument('--'+flag,type=Path,required=True)
    imp.add_argument('--role',choices=('primary','p4','final'),required=True)
    imp.add_argument('--split',choices=('dev','test'),required=True)
    imp.add_argument('--comparison',type=Path)
    imp.add_argument('--finalize',action='store_true')
    compare=commands.add_parser('review-compare',help='Keep raw judgements separate; export human final template')
    for flag in ('run','bundle','primary','p4','output-dir'):compare.add_argument('--'+flag,type=Path,required=True)
    compare.add_argument('--split',choices=('dev','test'),required=True)
    for name in ('validate-labels','freeze','metrics'):
        sub=commands.add_parser(name)
        for flag in ('run','primary','cross','final','approval'):
            sub.add_argument('--'+flag,type=Path,required=True)
        if name!='freeze':sub.add_argument('--split',choices=('dev','test'),required=True)
        if name!='validate-labels':sub.add_argument('--output',type=Path,required=True)
        if name=='metrics':
            sub.add_argument('--freeze',type=Path)
            sub.add_argument('--authorization',type=Path)
    args=parser.parse_args()
    if args.command=='revise-scenarios':
        from src.evaluation.revision import revise_scenarios
        revision=revise_scenarios(args.run,args.cases,args.output_dir,label_files=args.label_file)
        result={key:revision[key] for key in ('scenario_version','changed_scenarios','rankings_recomputed','label_review_required')}
    elif args.command in ('pool','review-export'):
        from src.config import settings
        from src.services.recommendation_snapshot import load_recommendation_snapshot
        path=args.snapshot.resolve()
        # This command owns its offline process; no active pointer is changed.
        settings.SMARTLIBAI_DEMO_SNAPSHOT=str(path)
        settings.CLASSROOM_DEMO_SNAPSHOT=None
        data=read_cases(args.cases if args.command=='pool' else args.run/'scenarios.json')
        source=load_recommendation_snapshot(data['snapshot_id'],deadline=monotonic()+120)
        if args.command=='pool':
            run=create_pool(source,path,args.cases,args.output_dir)
            result={key:run[key] for key in ('snapshot_id','catalog_books','corpus_books','corpus_works','pool_pairs','review_pairs','status')}
        else:
            from src.evaluation.review import export_review
            exported=export_review(args.run,source,path,args.output_dir)
            result=dict(status='exported_unapproved',counts=exported['counts'],output=str(args.output_dir))
    elif args.command=='review-import':
        from src.evaluation.review import import_review
        result=import_review(args.run,args.bundle,args.input,args.role,args.split,args.output_dir,
            finalize=args.finalize,comparison=args.comparison)
    elif args.command=='review-compare':
        from src.evaluation.review import compare_reviews
        result=compare_reviews(args.run,args.bundle,args.primary,args.p4,args.split,args.output_dir)
    else:
        common=dict(primary=args.primary,cross=args.cross,final=args.final,approval=args.approval)
        if args.command=='validate-labels':
            labels=validate_labels(args.run,split=args.split,**common)
            result=dict(status='valid',split=args.split,pairs=len(labels))
            approved=json.loads(args.approval.read_text(encoding='utf-8-sig'))
            if approved.get('protocol')=='c31-c33-v2-joint-review-test':
                result.update(protocol=approved['protocol'],
                    validation_basis='joint_review_exception' if args.split=='test' else 'original_dev_review',
                    original_independent_test_protocol_satisfied=False,spec_acceptance_claim=False)
        elif args.command=='freeze':
            freeze(args.run,output=args.output,**common);result=dict(status='frozen',output=str(args.output))
        else:
            report=evaluate(args.run,split=args.split,output=args.output,frozen=args.freeze,authorization=args.authorization,**common)
            result=dict(split=report['split'],case_count=report['case_count'],macro=report['macro'])
    print(json.dumps(result,ensure_ascii=True,indent=2))


if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError) as exc:
        raise SystemExit(f'Evaluation refused: {exc}')
