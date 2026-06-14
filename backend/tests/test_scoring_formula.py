"""Tests unitarios de la fórmula de scoring (no requieren BD)."""

from app.core.config import ScoringWeights
from app.services.scoring import FactorBreakdown
from app.services.supercell import proficiency_score


def test_proficiency_score_max_values() -> None:
    score = proficiency_score(
        trophies=1000,
        trophies_max=1000,
        power_level=11,
        gadgets_unlocked=2,
        star_powers_unlocked=2,
        recent_winrate=1.0,
    )
    assert score == 100.0


def test_proficiency_score_zero() -> None:
    score = proficiency_score(
        trophies=0,
        trophies_max=1000,
        power_level=1,
        gadgets_unlocked=0,
        star_powers_unlocked=0,
        recent_winrate=0.0,
    )
    # 0.20 * (1/11) ≈ 1.8 (sólo aporta power level mínimo)
    assert 0.0 <= score <= 5.0


def test_factor_breakdown_as_dict_keys() -> None:
    f = FactorBreakdown(winrate_mapa=0.6, counter_score=0.2)
    d = f.as_dict()
    assert set(d.keys()) == {
        "winrate_mapa",
        "counter_score",
        "sinergia",
        "pickrate_relativo",
        "ban_risk",
        "counterable",
        "personal_proficiency",
    }


def test_default_weights_have_expected_signs() -> None:
    w = ScoringWeights()
    # los siete pesos son no negativos; los signos (+/-) los aplica la fórmula
    for name in (
        "w1_winrate_mapa",
        "w2_counter_score",
        "w3_sinergia",
        "w4_pickrate_relativo",
        "w5_ban_risk",
        "w6_counterable",
        "w7_personal_proficiency",
    ):
        assert getattr(w, name) >= 0.0
