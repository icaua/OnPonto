(function (root) {
  "use strict";

  var PT_BR = "pt-BR";
  var DEFAULT_TIME_ZONE = "America/Sao_Paulo";
  var EMPTY_TIME_MARKERS = ["", "-", "--", "—", "–"];

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (character) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#039;",
      }[character];
    });
  }

  function deepFreeze(value, seen) {
    if (value === null || (typeof value !== "object" && typeof value !== "function")) {
      return value;
    }

    var visited = seen || new WeakSet();
    if (visited.has(value)) return value;
    visited.add(value);

    Reflect.ownKeys(value).forEach(function (key) {
      deepFreeze(value[key], visited);
    });
    return Object.freeze(value);
  }

  function safeClone(value, seen) {
    if (value === null || typeof value !== "object") return value;

    var visited = seen || new WeakMap();
    if (visited.has(value)) return visited.get(value);

    if (value instanceof Date) return new Date(value.getTime());
    if (value instanceof RegExp) return new RegExp(value.source, value.flags);

    if (value instanceof Map) {
      var mapCopy = new Map();
      visited.set(value, mapCopy);
      value.forEach(function (mapValue, mapKey) {
        mapCopy.set(safeClone(mapKey, visited), safeClone(mapValue, visited));
      });
      return mapCopy;
    }

    if (value instanceof Set) {
      var setCopy = new Set();
      visited.set(value, setCopy);
      value.forEach(function (setValue) {
        setCopy.add(safeClone(setValue, visited));
      });
      return setCopy;
    }

    var copy = Array.isArray(value) ? [] : Object.create(Object.getPrototypeOf(value));
    visited.set(value, copy);
    Reflect.ownKeys(value).forEach(function (key) {
      if (Array.isArray(value) && key === "length") return;
      copy[key] = safeClone(value[key], visited);
    });
    return copy;
  }

  function pad2(value) {
    return String(Math.abs(Number(value) || 0)).padStart(2, "0");
  }

  function parseTimeInput(value, options) {
    var settings = options || {};
    var original = value;
    var raw = value == null ? "" : String(value).trim();
    var empty = EMPTY_TIME_MARKERS.indexOf(raw) !== -1;

    if (empty) {
      return {
        input: original,
        empty: true,
        valid: true,
        normalized: "",
        normalizedWithSeconds: "",
        hours: null,
        minutesPart: null,
        seconds: null,
        totalMinutes: null,
        unusual: false,
        warning: "",
        code: null,
        error: "",
      };
    }

    var hours;
    var minutes;
    var seconds = 0;
    var colonMatch = raw.match(/^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$/);

    if (colonMatch) {
      hours = Number(colonMatch[1]);
      minutes = Number(colonMatch[2]);
      seconds = colonMatch[3] == null ? 0 : Number(colonMatch[3]);
    } else if (/^\d{1,4}$/.test(raw)) {
      if (raw.length <= 2) {
        hours = Number(raw);
        minutes = 0;
      } else if (raw.length === 3) {
        hours = Number(raw.slice(0, 1));
        minutes = Number(raw.slice(1));
      } else {
        hours = Number(raw.slice(0, 2));
        minutes = Number(raw.slice(2));
      }
    } else {
      return invalidTimeResult(original, "invalid_format", "Use um horário no formato 08:00, 8:00, 0800 ou 800.");
    }

    if (hours > 23 || minutes > 59 || seconds > 59) {
      return invalidTimeResult(original, "out_of_range", "Horário impossível. Use horas de 00 a 23 e minutos de 00 a 59.");
    }

    var totalMinutes = hours * 60 + minutes;
    var unusualStart = Number.isFinite(settings.unusualStartMinutes) ? settings.unusualStartMinutes : 5 * 60;
    var unusualEnd = Number.isFinite(settings.unusualEndMinutes) ? settings.unusualEndMinutes : 23 * 60;
    var unusual = totalMinutes < unusualStart || totalMinutes >= unusualEnd;
    var normalized = pad2(hours) + ":" + pad2(minutes);
    var normalizedWithSeconds = normalized + ":" + pad2(seconds);

    return {
      input: original,
      empty: false,
      valid: true,
      normalized: normalized,
      normalizedWithSeconds: normalizedWithSeconds,
      hours: hours,
      minutesPart: minutes,
      seconds: seconds,
      totalMinutes: totalMinutes,
      unusual: unusual,
      warning: unusual ? "Horário incomum; confirme se " + normalized + " está correto." : "",
      code: null,
      error: "",
    };
  }

  function invalidTimeResult(original, code, message) {
    return {
      input: original,
      empty: false,
      valid: false,
      normalized: null,
      normalizedWithSeconds: null,
      hours: null,
      minutesPart: null,
      seconds: null,
      totalMinutes: null,
      unusual: false,
      warning: "",
      code: code,
      error: message,
    };
  }

  function normalizeTimeInput(value, options) {
    var result = parseTimeInput(value, options);
    if (!result.valid) {
      if (options && options.throwOnInvalid) {
        throw new RangeError(result.error);
      }
      return null;
    }
    if (result.empty) return "";
    return options && options.keepSeconds ? result.normalizedWithSeconds : result.normalized;
  }

  function validateTimeInput(value, options) {
    return parseTimeInput(value, options);
  }

  function isValidTime(value, options) {
    var result = parseTimeInput(value, options);
    return result.valid && (options && options.allowEmpty === false ? !result.empty : true);
  }

  function isUnusualTime(value, options) {
    var result = parseTimeInput(value, options);
    return result.valid && !result.empty && result.unusual;
  }

  function getUnusualTimeWarning(value, options) {
    return parseTimeInput(value, options).warning;
  }

  function timeToMinutes(value) {
    if (typeof value === "number" && Number.isFinite(value)) return Math.round(value);
    var result = parseTimeInput(value);
    return result.valid && !result.empty ? result.totalMinutes : null;
  }

  function durationToMinutes(value) {
    if (typeof value === "number" && Number.isFinite(value)) return Math.round(value);
    if (value == null || value === "") return null;

    var raw = String(value).trim();
    var sign = 1;
    if (raw.charAt(0) === "+" || raw.charAt(0) === "-") {
      sign = raw.charAt(0) === "-" ? -1 : 1;
      raw = raw.slice(1);
    }
    var match = raw.match(/^(\d+):(\d{2})$/);
    if (!match || Number(match[2]) > 59) return null;
    return sign * (Number(match[1]) * 60 + Number(match[2]));
  }

  function formatDuration(minutes, options) {
    var settings = options || {};
    if (minutes == null || !Number.isFinite(Number(minutes))) return settings.emptyValue || "—";

    var rounded = Math.round(Number(minutes));
    var negative = rounded < 0;
    var absolute = Math.abs(rounded);
    var hours = Math.floor(absolute / 60);
    var minutePart = absolute % 60;
    var sign = "";

    if (negative) sign = "-";
    else if (settings.signed && rounded > 0) sign = "+";

    return sign + String(hours).padStart(settings.minHourDigits || 2, "0") + ":" + pad2(minutePart);
  }

  function formatBalance(minutes, emptyValue) {
    return formatDuration(minutes, { signed: true, emptyValue: emptyValue || "—" });
  }

  function normalizePunchList(input) {
    if (Array.isArray(input)) return input.slice();
    if (!input || typeof input !== "object") return [];

    return [
      input.entry != null ? input.entry : input.entrada,
      input.breakStart != null ? input.breakStart : input.saidaIntervalo != null ? input.saidaIntervalo : input.saida_intervalo,
      input.breakEnd != null ? input.breakEnd : input.retorno != null ? input.retorno : input.retorno_intervalo,
      input.exit != null ? input.exit : input.saida,
    ];
  }

  function calculateWorkedMinutes(input, options) {
    var settings = options || {};
    var rawPunches = normalizePunchList(input);
    var punches = [];

    rawPunches.forEach(function (punch) {
      if (punch === null || punch === undefined || EMPTY_TIME_MARKERS.indexOf(String(punch).trim()) !== -1) return;
      punches.push(punch);
    });

    if (!punches.length || punches.length % 2 !== 0) return null;

    var total = 0;
    for (var index = 0; index < punches.length; index += 2) {
      var start = timeToMinutes(punches[index]);
      var end = timeToMinutes(punches[index + 1]);
      if (start == null || end == null) return null;
      if (end < start && settings.allowOvernight !== false) end += 24 * 60;
      if (end < start) return null;
      total += end - start;
    }
    return total;
  }

  function calculateBalance(workedMinutes, expectedMinutes) {
    var worked = durationToMinutes(workedMinutes);
    var expected = durationToMinutes(expectedMinutes);
    if (worked == null || expected == null) return null;
    return worked - expected;
  }

  function calculateJourney(input, expected, options) {
    var punches = normalizePunchList(input);
    var presentPunches = punches.filter(function (punch) {
      return punch !== null && punch !== undefined && EMPTY_TIME_MARKERS.indexOf(String(punch).trim()) === -1;
    });
    var invalidPunches = presentPunches.filter(function (punch) {
      return !isValidTime(punch, { allowEmpty: false });
    });
    var expectedMinutes = durationToMinutes(expected);
    var workedMinutes = invalidPunches.length ? null : calculateWorkedMinutes(presentPunches, options);
    var incomplete = presentPunches.length % 2 !== 0;
    var balanceMinutes = workedMinutes == null || expectedMinutes == null ? null : workedMinutes - expectedMinutes;

    return {
      punches: punches,
      punchCount: presentPunches.length,
      workedMinutes: workedMinutes,
      expectedMinutes: expectedMinutes,
      balanceMinutes: balanceMinutes,
      worked: formatDuration(workedMinutes),
      expected: formatDuration(expectedMinutes),
      balance: formatBalance(balanceMinutes),
      incomplete: incomplete,
      valid: invalidPunches.length === 0 && !incomplete,
      invalidPunches: invalidPunches,
    };
  }

  function parseIsoDateParts(value) {
    if (value == null || value === "") return null;
    var match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!match) return null;
    var year = Number(match[1]);
    var month = Number(match[2]);
    var day = Number(match[3]);
    var date = new Date(Date.UTC(year, month - 1, day));
    if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
    return { year: year, month: month, day: day, date: date };
  }

  function formatDate(value, options) {
    var settings = options || {};
    var parts = parseIsoDateParts(value);
    if (!parts) return settings.emptyValue || "—";
    if (settings.short) return pad2(parts.day) + "/" + pad2(parts.month);
    return pad2(parts.day) + "/" + pad2(parts.month) + "/" + parts.year;
  }

  function formatWeekday(value, options) {
    var settings = options || {};
    var parts = parseIsoDateParts(value);
    if (!parts) return settings.emptyValue || "—";
    var weekday = new Intl.DateTimeFormat(settings.locale || PT_BR, {
      weekday: settings.long ? "long" : "short",
      timeZone: "UTC",
    }).format(parts.date);
    weekday = weekday.replace(".", "");
    return settings.capitalize === false ? weekday : weekday.charAt(0).toUpperCase() + weekday.slice(1);
  }

  function formatDayLabel(value) {
    var parts = parseIsoDateParts(value);
    if (!parts) return "—";
    return pad2(parts.day) + " " + formatWeekday(value);
  }

  function formatDateTime(value, options) {
    var settings = options || {};
    if (value == null || value === "") return settings.emptyValue || "—";
    var date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return settings.emptyValue || "—";
    var formatted = new Intl.DateTimeFormat(settings.locale || PT_BR, {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: settings.timeZone || DEFAULT_TIME_ZONE,
    }).format(date);
    return formatted.replace(",", " às");
  }

  function formatCompetence(competenceOrMonth, year) {
    if (competenceOrMonth && typeof competenceOrMonth === "object") {
      year = competenceOrMonth.year != null ? competenceOrMonth.year : competenceOrMonth.ano;
      competenceOrMonth = competenceOrMonth.month != null ? competenceOrMonth.month : competenceOrMonth.mes;
    }
    if (!competenceOrMonth || !year) return "—";
    return pad2(competenceOrMonth) + "/" + year;
  }

  function formatPercentage(value, options) {
    var settings = options || {};
    if (value == null || !Number.isFinite(Number(value))) return settings.emptyValue || "—";
    var number = Number(value);
    if (settings.fraction === true || (settings.fraction !== false && Math.abs(number) <= 1)) number *= 100;
    return new Intl.NumberFormat(settings.locale || PT_BR, {
      maximumFractionDigits: settings.maximumFractionDigits == null ? 0 : settings.maximumFractionDigits,
      minimumFractionDigits: settings.minimumFractionDigits == null ? 0 : settings.minimumFractionDigits,
    }).format(number) + "%";
  }

  function formatNumber(value, options) {
    if (value == null || !Number.isFinite(Number(value))) return options && options.emptyValue ? options.emptyValue : "—";
    return new Intl.NumberFormat((options && options.locale) || PT_BR, options || {}).format(Number(value));
  }

  function formatFileSize(bytes, options) {
    var settings = options || {};
    var value = Number(bytes);
    if (!Number.isFinite(value) || value < 0) return settings.emptyValue || "—";
    if (value === 0) return "0 B";
    var units = ["B", "KB", "MB", "GB"];
    var unitIndex = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
    var amount = value / Math.pow(1024, unitIndex);
    return new Intl.NumberFormat(settings.locale || PT_BR, {
      maximumFractionDigits: unitIndex === 0 ? 0 : 1,
    }).format(amount) + " " + units[unitIndex];
  }

  function statusKey(value) {
    return String(value == null ? "" : value)
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  function joinNaturalLanguage(items) {
    var values = (items || []).filter(function (item) { return item !== null && item !== undefined && item !== ""; });
    if (!values.length) return "";
    if (values.length === 1) return String(values[0]);
    return values.slice(0, -1).join(", ") + " e " + values[values.length - 1];
  }

  var api = {
    escapeHtml: escapeHtml,
    escape: escapeHtml,
    deepFreeze: deepFreeze,
    safeClone: safeClone,
    cloneSafe: safeClone,
    cloneSeguro: safeClone,
    parseTimeInput: parseTimeInput,
    parseTime: parseTimeInput,
    normalizeTimeInput: normalizeTimeInput,
    normalizeTime: normalizeTimeInput,
    normalizarHorario: normalizeTimeInput,
    validateTimeInput: validateTimeInput,
    validateTime: validateTimeInput,
    validarHorario: validateTimeInput,
    isValidTime: isValidTime,
    isUnusualTime: isUnusualTime,
    getUnusualTimeWarning: getUnusualTimeWarning,
    alertaHorarioIncomum: getUnusualTimeWarning,
    timeToMinutes: timeToMinutes,
    durationToMinutes: durationToMinutes,
    formatDuration: formatDuration,
    formatBalance: formatBalance,
    calculateWorkedMinutes: calculateWorkedMinutes,
    calculateBalance: calculateBalance,
    calculateJourney: calculateJourney,
    calcularJornada: calculateJourney,
    formatDate: formatDate,
    formatWeekday: formatWeekday,
    formatDayLabel: formatDayLabel,
    formatDateTime: formatDateTime,
    formatCompetence: formatCompetence,
    formatPercentage: formatPercentage,
    formatNumber: formatNumber,
    formatFileSize: formatFileSize,
    statusKey: statusKey,
    joinNaturalLanguage: joinNaturalLanguage,
  };

  root.OnPontoUtils = Object.freeze(api);
})(typeof window !== "undefined" ? window : globalThis);
