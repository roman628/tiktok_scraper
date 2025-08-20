- we had a lot of stuff in this codebase and it was mostly clutter, I am trying to rebuild the system to match the diagram.png image contained here [Image #1], the pipeline will be as follows

firefox extension -> urls.txt -> robust_master_downloader (collector.py) -> master2.json -> clean data -> get insights and train ML model

- the goal is to move everything out of keep/ to a permanent project layout, a system that is simply dockerized so this system can be portable. The purpose of this system should be able to run nearly everything automatically, with the only input being the urls from the users extension. The output being the updated snoo model, and the data and insights that come from it

the ideal layout:

extension/
    (contains the firefox_extension/ stuff)
model/
    api.py
    start_api.sh
    models/
        snoo.pkl
data/
    urls.txt
    master2.json
scripts/
    collector.py
    train_ml.py
dashboard/
    frontend stuff for the dashboard
docker-compose
docker
requirements.txt
README.md
diagram.png
.gitignore


as we develop this out, ensure that the changes are respecting this, it should remain very clean throughout