# Trained model files

This is where you should store the trained model files
There should be a corresponding config file in ../config/ for each language

By default it will be empty until you run the train command equivalent to your config files, so something such as:

    python -m rasa_nlu.train -c config/mlb_config_fr.json
    python -m rasa_nlu.train -c config/mlb_config_en.json

NB: Training requires the corresponding spaCy models for each language as well as the corresponding config file
See ../README.md for basic installation details and spaCy documenation for further details: https://spacy.io/usage/models
