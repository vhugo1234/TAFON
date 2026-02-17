# -*- coding: utf-8 -*-
# backend/app/utils/grouping_algorithm.py

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, date, time as dtime
from types import SimpleNamespace
import logging

from app.schemas.candidate_schema import CandidateOut, TurmaInfo, GroupingConfig

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)  # ative localmente se quiser ver listas completas


def _normalize_config_for_algorithm(raw_config: Any) -> SimpleNamespace:
    data: Dict[str, Any] = {}
    try:
        if hasattr(raw_config, "model_dump"):
            data = raw_config.model_dump()
        elif isinstance(raw_config, dict):
            data = dict(raw_config)
        else:
            data = getattr(raw_config, "__dict__", {}) or {}
    except Exception:
        data = {}

    # legacy alias: batch_size -> group_size
    if data.get("group_size") is None and data.get("batch_size") is not None:
        data["group_size"] = data.get("batch_size")
    if data.get("group_size") is not None:
        try:
            data["group_size"] = int(data["group_size"])
        except Exception:
            data["group_size"] = None

    # distribution / sort aliases
    if "distribution_mode" not in data and "distributionMode" in data:
        data["distribution_mode"] = data.get("distributionMode")
    if "sort_by_registration" not in data and "sortByRegistration" in data:
        data["sort_by_registration"] = data.get("sortByRegistration", True)
    if "registration_order" not in data and "registrationOrder" in data:
        data["registration_order"] = data.get("registrationOrder", "asc")

    data["sort_by_registration"] = data.get("sort_by_registration", True)
    data["registration_order"] = data.get("registration_order", "asc")
    data["distribution_mode"] = data.get("distribution_mode", "balanced")
    data["allow_partial_groups"] = data.get("allow_partial_groups", True)

    data["separate_by_gender"] = data.get("separate_by_gender", False)
    data["gender_priority"] = data.get("gender_priority", None)

    # scheduling aliases (accept multiple frontend names)
    if "start_time" not in data or not data.get("start_time"):
        for alias in ("morning_start", "morningStart", "start_time", "startTime"):
            if alias in data and data.get(alias):
                val = data.get(alias)
                if isinstance(val, str):
                    data["start_time"] = val
                    break

    if "interval_minutes" not in data or data.get("interval_minutes") is None:
        for alias in ("interval_between_batches", "intervalMinutes", "interval_minutes"):
            if alias in data and data.get(alias) is not None:
                try:
                    data["interval_minutes"] = int(data.get(alias))
                except Exception:
                    data["interval_minutes"] = None
                break

    # morning/afternoon bounds aliases
    if "morning_end_limit" not in data and "morningEndLimit" in data:
        data["morning_end_limit"] = data.get("morningEndLimit")
    if "afternoon_start_min" not in data and "afternoonStartMin" in data:
        data["afternoon_start_min"] = data.get("afternoonStartMin")
    if "afternoon_end_limit" not in data and "afternoonEndLimit" in data:
        data["afternoon_end_limit"] = data.get("afternoonEndLimit")

    # group_duration explicit (preferred) and slot_duration (legacy)
    if "group_duration" not in data and "groupDuration" in data:
        try:
            data["group_duration"] = int(data.get("groupDuration"))
        except Exception:
            data["group_duration"] = data.get("groupDuration")
    if "slot_duration" not in data and "slotDuration" in data:
        try:
            data["slot_duration"] = int(data.get("slotDuration"))
        except Exception:
            data["slot_duration"] = data.get("slotDuration")

    data.setdefault("group_size", None)
    data.setdefault("interval_minutes", None)
    data.setdefault("start_time", None)
    data.setdefault("morning_end_limit", None)
    data.setdefault("afternoon_start_min", None)
    data.setdefault("afternoon_end_limit", None)
    data.setdefault("group_duration", None)
    data.setdefault("slot_duration", None)

    # days normalization -> list of iso strings
    if "days" in data and data.get("days") is not None:
        days_raw = data.get("days")
        days_clean: List[str] = []
        if isinstance(days_raw, list):
            for d in days_raw:
                if isinstance(d, str):
                    days_clean.append(d)
                elif isinstance(d, (date, datetime)):
                    days_clean.append(d.date().isoformat() if isinstance(d, datetime) else d.isoformat())
        data["days"] = days_clean
    else:
        data.setdefault("days", None)

    return SimpleNamespace(**data)


def _parse_time_str(ts: str) -> Optional[dtime]:
    try:
        hh, mm = map(int, ts.split(':'))
        return dtime(hour=hh, minute=mm)
    except Exception:
        return None


def _generate_start_slots_for_block_on_day(
    day: date,
    block_start: str,
    interval_minutes: int,
    block_end_limit: str
) -> List[str]:
    """
    Generate start times (HH:MM) for a specific day.
    Starts occur every `interval_minutes`. A start is included while
    start <= block_end_limit (we do not check duration).
    """
    slots: List[str] = []
    start_t = _parse_time_str(block_start)
    end_t = _parse_time_str(block_end_limit)
    if not start_t or not end_t or interval_minutes is None:
        return []

    current = datetime.combine(day, start_t)
    end_limit = datetime.combine(day, end_t)
    step = timedelta(minutes=interval_minutes)

    while current <= end_limit:
        slots.append(current.strftime('%H:%M'))
        current = current + step

    return slots


def _build_days_list(cfg: SimpleNamespace) -> List[date]:
    days_in = getattr(cfg, "days", None)
    sd = getattr(cfg, "start_date", None)
    dc = getattr(cfg, "days_count", None)

    result: List[date] = []
    if days_in and isinstance(days_in, list) and len(days_in) > 0:
        for ds in days_in:
            try:
                dobj = datetime.fromisoformat(ds).date()
            except Exception:
                try:
                    dobj = datetime.strptime(ds, "%Y-%m-%d").date()
                except Exception:
                    continue
            result.append(dobj)
        return result

    if sd:
        try:
            first = datetime.fromisoformat(sd).date()
        except Exception:
            try:
                first = datetime.strptime(sd, "%Y-%m-%d").date()
            except Exception:
                first = datetime.now().date()
    else:
        first = datetime.now().date()

    count = int(dc) if (dc and isinstance(dc, int)) else 1
    for i in range(count):
        result.append(first + timedelta(days=i))
    return result


def _build_global_slots(cfg: SimpleNamespace) -> List[Tuple[date, str]]:
    """
    Build (date, 'HH:MM') slots.
    Generates start times for morning and afternoon blocks independently.
    Does NOT depend on group_duration/slot_duration to generate starts.
    """
    def _clean_time_str(s: Optional[str]) -> Optional[str]:
        if s is None:
            return None
        if not isinstance(s, str):
            try:
                return str(s)
            except Exception:
                return None
        s = s.strip()
        return s or None

    interval_raw = getattr(cfg, "interval_minutes", None)
    try:
        interval = int(interval_raw) if interval_raw is not None else None
    except Exception:
        try:
            interval = int(str(interval_raw).strip())
        except Exception:
            interval = None

    morning_start = _clean_time_str(getattr(cfg, "morning_start", None) or getattr(cfg, "start_time", None))
    morning_end = _clean_time_str(getattr(cfg, "morning_end_limit", None))
    afternoon_start = _clean_time_str(getattr(cfg, "afternoon_start_min", None))
    afternoon_end = _clean_time_str(getattr(cfg, "afternoon_end_limit", None))

    # fallback: se veio afternoon_start mas não veio afternoon_end, assumimos um limite razoável
    if afternoon_start and not afternoon_end:
        logger.warning("afternoon_start provided but afternoon_end missing; using fallback '18:30'")
        afternoon_end = "18:30"

    logger.warning(
        "Scheduling cfg (build_global_slots): interval=%s morning_start=%s morning_end=%s afternoon_start=%s afternoon_end=%s days=%s",
        interval, morning_start, morning_end, afternoon_start, afternoon_end, getattr(cfg, "days", None)
    )

    # Need interval and at least one block
    if interval is None or (not morning_start and not afternoon_start):
        logger.warning("Insufficient scheduling config: missing interval or no time blocks defined")
        return []

    days = _build_days_list(cfg)
    slots: List[Tuple[date, str]] = []

    for d in days:
        morning_slots: List[str] = []
        afternoon_slots: List[str] = []

        if morning_start and morning_end:
            try:
                morning_slots = _generate_start_slots_for_block_on_day(d, morning_start, interval, morning_end)
            except Exception as e:
                logger.exception("Erro gerando morning_slots for day %s: %s", d, e)
                morning_slots = []

        if afternoon_start and afternoon_end:
            try:
                afternoon_slots = _generate_start_slots_for_block_on_day(d, afternoon_start, interval, afternoon_end)
            except Exception as e:
                logger.exception("Erro gerando afternoon_slots for day %s: %s", d, e)
                afternoon_slots = []

        logger.warning("Day %s morning_slots=%s", d.isoformat(), morning_slots)
        logger.warning("Day %s afternoon_slots=%s", d.isoformat(), afternoon_slots)

        # append morning then afternoon — ensures "close day" behavior when assigning later
        for t in morning_slots:
            slots.append((d, t))
        for t in afternoon_slots:
            slots.append((d, t))

    logger.warning("Generated %d slots across %d days", len(slots), len(days))
    return slots


def _create_turma_info(
    candidates: List[CandidateOut],
    group_number: int,
    gender_filter: str = None
) -> TurmaInfo:
    gender_dist = {'M': 0, 'F': 0}
    for candidate in candidates:
        gender_dist[candidate.gender] = gender_dist.get(candidate.gender, 0) + 1

    if gender_filter:
        group_name = f"Turma {group_number:02d} - {'Masculino' if gender_filter == 'M' else 'Feminino'}"
    else:
        group_name = f"Turma {group_number:02d}"

    return TurmaInfo(
        name=group_name,
        start_time=None,
        end_time=None,
        date=None,
        candidates=candidates,
        total_candidates=len(candidates),
        gender_distribution=gender_dist
    )


def _assign_times(
    groups: List[TurmaInfo],
    cfg: SimpleNamespace
) -> List[TurmaInfo]:
    """
    Assign times to groups packing by day: fill all slots of day1 (morning+afternoon)
    before using day2. Only sets start_time and date (no duration/end_time logic).
    """
    slots = _build_global_slots(cfg)
    logger.warning("DEBUG _assign_times: groups_count=%d slots_total=%d", len(groups), len(slots))
    logger.warning("DEBUG _assign_times slots_sample=%s", [(d.isoformat(), t) for d, t in slots[:200]])
    logger.warning("DEBUG _assign_times groups_before_mapping=%s", [g.name for g in groups[:60]])
    if not slots:
        logger.warning("No slots generated - leaving groups without times")
        logger.warning("DEBUG _assign_times mapping_result_sample=%s", [(g.name, g.date, g.start_time) for g in groups[:60]])
        return groups

    # Group slots by day preserving the order returned by _build_global_slots
    slots_by_day: Dict[date, List[str]] = {}
    for d, t in slots:
        slots_by_day.setdefault(d, []).append(t)

    ordered_days = sorted(slots_by_day.keys())

    group_idx = 0
    assigned_per_day: Dict[str, int] = {}
    for day_obj in ordered_days:
        times = slots_by_day.get(day_obj, [])
        assigned_today = 0
        for time_str in times:
            if group_idx >= len(groups):
                break
            grp = groups[group_idx]
            # set date and start_time (only start_time matters)
            try:
                grp.date = day_obj.isoformat()
            except Exception:
                grp.date = str(day_obj)
            grp.start_time = time_str
            grp.end_time = None  # explicit: we don't use end_time

            group_idx += 1
            assigned_today += 1

        assigned_per_day[day_obj.isoformat()] = assigned_today
        logger.warning("Assigned %d groups to day %s", assigned_today, day_obj.isoformat())

        if group_idx >= len(groups):
            break

    remaining = max(0, len(groups) - group_idx)
    if remaining > 0:
        logger.warning("Slots exhausted: %d groups remain without times", remaining)
        for i in range(group_idx, len(groups)):
            groups[i].date = None
            groups[i].start_time = None
            groups[i].end_time = None

    logger.warning("DEBUG _assign_times mapping_result_sample=%s", [(g.name, g.date, g.start_time) for g in groups[:60]])
    logger.warning("Finished assigning times. Days used: %s", list(assigned_per_day.items()))
    return groups


def _assign_sequence_numbers(groups: List[TurmaInfo], separate_by_gender: bool) -> None:
    if not separate_by_gender:
        counter = 1
        for grp in groups:
            for cand in grp.candidates:
                cand.batch_number = counter
                counter += 1
    else:
        counters = {"F": 1, "M": 1}
        for grp in groups:
            grp_gender = None
            if isinstance(grp.name, str):
                if "Masculino" in grp.name:
                    grp_gender = "M"
                elif "Feminino" in grp.name:
                    grp_gender = "F"
            if grp_gender in ("F", "M"):
                for cand in grp.candidates:
                    cand.batch_number = counters[grp_gender]
                    counters[grp_gender] += 1
            else:
                for cand in grp.candidates:
                    g = cand.gender if getattr(cand, "gender", None) in ("M", "F") else "M"
                    cand.batch_number = counters[g]
                    counters[g] += 1


def group_candidates(
    candidates: List[CandidateOut],
    config: GroupingConfig
) -> List[TurmaInfo]:
    groups: List[TurmaInfo] = []
    cfg = _normalize_config_for_algorithm(config)
    logger.warning("DEBUG group_candidates: cfg keys=%s", list(cfg.__dict__.keys()))
    logger.warning("DEBUG group_candidates: interval_minutes=%s morning_start=%s afternoon_start_min=%s days=%s",
                getattr(cfg, "interval_minutes", None),
                getattr(cfg, "morning_start", None),
                getattr(cfg, "afternoon_start_min", None),
                getattr(cfg, "days", None))
    sorted_candidates = _sort_candidates(candidates, cfg)

    # grouping
    if getattr(cfg, "separate_by_gender", False):
        if cfg.gender_priority == 'F':
            female_candidates = [c for c in sorted_candidates if c.gender == 'F']
            male_candidates = [c for c in sorted_candidates if c.gender == 'M']
            female_groups = _create_groups(female_candidates, cfg, 'F')
            male_groups = _create_groups(male_candidates, cfg, 'M')
            groups.extend(female_groups); groups.extend(male_groups)
        elif cfg.gender_priority == 'M':
            male_candidates = [c for c in sorted_candidates if c.gender == 'M']
            female_candidates = [c for c in sorted_candidates if c.gender == 'F']
            male_groups = _create_groups(male_candidates, cfg, 'M')
            female_groups = _create_groups(female_candidates, cfg, 'F')
            groups.extend(male_groups); groups.extend(female_groups)
        else:
            male_candidates = [c for c in sorted_candidates if c.gender == 'M']
            female_candidates = [c for c in sorted_candidates if c.gender == 'F']
            male_groups = _create_groups(male_candidates, cfg, 'M')
            female_groups = _create_groups(female_candidates, cfg, 'F')
            groups.extend(male_groups); groups.extend(female_groups)
    else:
        if cfg.gender_priority == 'F':
            ordering = sorted(sorted_candidates, key=lambda c: (0 if c.gender == 'F' else 1, c.registration_number))
            groups.extend(_create_groups(ordering, cfg))
        elif cfg.gender_priority == 'M':
            ordering = sorted(sorted_candidates, key=lambda c: (0 if c.gender == 'M' else 1, c.registration_number))
            groups.extend(_create_groups(ordering, cfg))
        else:
            groups.extend(_create_groups(sorted_candidates, cfg))

    _assign_sequence_numbers(groups, getattr(cfg, "separate_by_gender", False))

    # IMPORTANT: schedule assignment should be triggered when we have a start (morning/afternoon) AND an interval.
    # We DO NOT require group_duration/slot_duration to assign start times — start times are input points only.
    if (getattr(cfg, "morning_start", None) or getattr(cfg, "start_time", None) or getattr(cfg, "afternoon_start_min", None)) and getattr(cfg, "interval_minutes", None):
        groups = _assign_times(groups, cfg)

    return groups


def _strip_accents(s: str) -> str:
    """Remove acentos/diacríticos e faz trim; retorna string normalizada em lower-case."""
    if not s:
        return ""
    # Normaliza para decomposed form e remove marcas de combinação (acentos)
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch)).lower().strip()

def _sort_candidates(
    candidates: List[Any],
    config: Any
) -> List[Any]:
    """
    Ordena candidates de forma determinística:
     - se sort_by_registration=True -> por registration_number (respeita asc/desc)
     - senão -> por ordering (ex: 'full_name'), usando comparação insensível a acentos e case.
    """
    # ordenar por inscrição quando pedido
    if getattr(config, "sort_by_registration", True):
        reverse = (getattr(config, "registration_order", "asc") == 'desc')
        try:
            return sorted(candidates, key=lambda c: (c.registration_number or ""), reverse=reverse)
        except Exception:
            return candidates

    # quando ordenar por nome completo
    ordering_field = getattr(config, "ordering", None)
    if ordering_field == "full_name":
        try:
            return sorted(candidates, key=lambda c: _strip_accents(getattr(c, "full_name", "") or ""))
        except Exception:
            return candidates

    # fallback: preservar ordem recebida
    return candidates


def _create_groups(
    candidates: List[CandidateOut],
    config: Any,
    gender_filter: str = None
) -> List[TurmaInfo]:
    groups = []
    group_size = getattr(config, "group_size", None)
    if not group_size or group_size <= 0:
        return groups
    mode = getattr(config, "distribution_mode", "balanced")
    if mode == 'balanced':
        total = len(candidates)
        if total == 0:
            return groups
        num_groups = (total + group_size - 1) // group_size
        avg_size = total // num_groups
        remainder = total % num_groups
        start_idx = 0
        for i in range(num_groups):
            current_size = avg_size + (1 if i < remainder else 0)
            if not getattr(config, "allow_partial_groups", True) and current_size < group_size:
                break
            end_idx = start_idx + current_size
            group_candidates = candidates[start_idx:end_idx]
            if group_candidates:
                groups.append(_create_turma_info(group_candidates, len(groups) + 1, gender_filter))
            start_idx = end_idx
    else:
        for i in range(0, len(candidates), group_size):
            group_candidates = candidates[i:i + group_size]
            if not getattr(config, "allow_partial_groups", True) and len(group_candidates) < group_size:
                break
            if group_candidates:
                groups.append(_create_turma_info(group_candidates, len(groups) + 1, gender_filter))
    return groups