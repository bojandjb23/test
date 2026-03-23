from .base_store import BaseStoreScraper
from .supplementstore_rs import SupplementStoreScraper
from .gymbeam_rs import GymBeamScraper
from .fitlab_rs import FitLabScraper
from .fourfit_rs import FourFitnessScraper
from .titaniumsport_rs import TitaniumSportScraper
from .proteini_si import ProteiniSiScraper
from .dobrobit_rs import DobrobitScraper
from .exyu_fitness import ExYuFitnessScraper

ALL_SCRAPERS = [
    SupplementStoreScraper,
    GymBeamScraper,
    FitLabScraper,
    FourFitnessScraper,
    TitaniumSportScraper,
    ProteiniSiScraper,
    DobrobitScraper,
    ExYuFitnessScraper,
]
