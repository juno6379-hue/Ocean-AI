"""Validate/register a frozen raw release and serve only on 127.0.0.1:8011."""
import argparse
from pathlib import Path

from app.ml.raw_forecast_development_server import ReleaseStore, canonical, create_app

DEFAULT_OUTPUT=Path('D:/AI_Observation/outputs/train-deploy-20261008')


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--deployment-root',type=Path,default=DEFAULT_OUTPUT/'deployment')
    parser.add_argument('--register',type=Path)
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args()
    store=ReleaseStore(args.deployment_root,allowed_source_roots=[Path('D:/AI_Observation/data_lake')])
    if args.register:
        pointer=store.register(args.register)
        print(canonical({'registered_release':pointer,'readiness':store.readiness()}).decode(),flush=True)
    if args.validate_only:
        print(canonical(store.details()).decode(),flush=True)
        return
    import uvicorn
    uvicorn.run(create_app(store),host='127.0.0.1',port=8011,access_log=False,proxy_headers=False)


if __name__=='__main__':main()
