# RS Supplement Deals

Aggregates supplement products from 8 popular Serbian online stores and displays them in a live discount dashboard.

## Stores

- Supplement Store (supplementstore.rs)
- GymBeam (gymbeam.rs)
- FitLab (fitlab.rs)
- 4Fitness (4fitness.rs)
- TitaniumSport (titaniumsport.rs)
- Proteini.si (rs.proteini.si)
- Dobrobit (dobrobit.rs)
- ExYu Fitness (exyu-fitness.rs)

## Usage

```bash
pip install -r requirements.txt

# Scrape all stores
python supplement_scraper.py

# Scrape specific stores
python supplement_scraper.py --stores GymBeam FitLab

# Scrape and serve dashboard locally
python supplement_scraper.py --serve --port 8000
```

## Live Dashboard

The dashboard is automatically deployed to GitHub Pages and updated every 6 hours.
