# -*- coding: utf-8 -*-
"""Hujjat/slayd matnlari uchun uch til: o'zbek, rus, ingliz."""

LANGS = ("uz", "ru", "en")

LANG_NAMES = {
    "uz": "O'zbekcha",
    "ru": "Русский",
    "en": "English",
}

LANG_FLAGS = {"uz": "\U0001f1fa\U0001f1ff", "ru": "\U0001f1f7\U0001f1fa", "en": "\U0001f1ec\U0001f1e7"}

T = {
    "uz": {
        "kind": {
            "mustaqil": "MUSTAQIL ISH",
            "referat": "REFERAT",
            "amaliy": "AMALIY HISOBOT",
            "tezis": "TEZIS",
            "maqola": "ILMIY MAQOLA",
            "prezentatsiya": "PREZENTATSIYA",
        },
        "ministry": "O'ZBEKISTON RESPUBLIKASI OLIY TA'LIM, FAN VA INNOVATSIYALAR VAZIRLIGI",
        "chair": "«{fan}» kafedrasi",
        "topic_word": "mavzusida",
        "student": "Bajardi",
        "group": "Guruh",
        "supervisor": "Tekshirdi",
        "toc": "MUNDARIJA",
        "toc_note": "Mundarijani yangilash uchun kursorni shu yerga qo'yib F9 tugmasini bosing",
        "intro": "KIRISH",
        "conclusion": "XULOSA",
        "references": "FOYDALANILGAN ADABIYOTLAR RO'YXATI",
        "figure": "{n}-rasm. {cap}",
        "table": "{n}-jadval. {cap}",
        "plan": "Reja",
        "thanks": "E'tiboringiz uchun rahmat!",
        "thanks_sub": "Savollar va takliflar uchun murojaat qilishingiz mumkin",
        "ai_directive": "",
    },
    "ru": {
        "kind": {
            "mustaqil": "САМОСТОЯТЕЛЬНАЯ РАБОТА",
            "referat": "РЕФЕРАТ",
            "amaliy": "ПРАКТИЧЕСКИЙ ОТЧЁТ",
            "tezis": "ТЕЗИС",
            "maqola": "НАУЧНАЯ СТАТЬЯ",
            "prezentatsiya": "ПРЕЗЕНТАЦИЯ",
        },
        "ministry": "МИНИСТЕРСТВО ВЫСШЕГО ОБРАЗОВАНИЯ, НАУКИ И ИННОВАЦИЙ РЕСПУБЛИКИ УЗБЕКИСТАН",
        "chair": "Кафедра «{fan}»",
        "topic_word": "на тему",
        "student": "Выполнил(а)",
        "group": "Группа",
        "supervisor": "Проверил(а)",
        "toc": "ОГЛАВЛЕНИЕ",
        "toc_note": "Для обновления оглавления установите курсор здесь и нажмите F9",
        "intro": "ВВЕДЕНИЕ",
        "conclusion": "ЗАКЛЮЧЕНИЕ",
        "references": "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ",
        "figure": "Рисунок {n}. {cap}",
        "table": "Таблица {n}. {cap}",
        "plan": "План",
        "thanks": "Спасибо за внимание!",
        "thanks_sub": "Готов(а) ответить на ваши вопросы",
        "ai_directive": (
            "Butun matnni faqat RUS TILIDA yoz (кириллица). Bo'lim va kichik bo'limlar "
            "nomi ham rus tilida bo'lsin. O'zbekcha so'z ishlatma."
        ),
    },
    "en": {
        "kind": {
            "mustaqil": "INDEPENDENT WORK",
            "referat": "ACADEMIC REPORT",
            "amaliy": "PRACTICAL REPORT",
            "tezis": "THESIS ABSTRACT",
            "maqola": "RESEARCH ARTICLE",
            "prezentatsiya": "PRESENTATION",
        },
        "ministry": "MINISTRY OF HIGHER EDUCATION, SCIENCE AND INNOVATIONS OF THE REPUBLIC OF UZBEKISTAN",
        "chair": "Department of {fan}",
        "topic_word": "on the topic",
        "student": "Prepared by",
        "group": "Group",
        "supervisor": "Supervisor",
        "toc": "CONTENTS",
        "toc_note": "Press F9 here to update the table of contents",
        "intro": "INTRODUCTION",
        "conclusion": "CONCLUSION",
        "references": "REFERENCES",
        "figure": "Figure {n}. {cap}",
        "table": "Table {n}. {cap}",
        "plan": "Outline",
        "thanks": "Thank you for your attention!",
        "thanks_sub": "I am happy to answer your questions",
        "ai_directive": (
            "Write the entire text ONLY in ENGLISH. All chapter and sub-chapter "
            "titles must be in English. Do not use Uzbek words."
        ),
    },
}


def norm(lang):
    lang = (lang or "uz").lower()
    return lang if lang in T else "uz"


def t(lang, key, **kw):
    lang = norm(lang)
    val = T[lang].get(key, T["uz"].get(key, ""))
    if kw:
        try:
            return val.format(**kw)
        except Exception:  # noqa: BLE001
            return val
    return val


def kind_title(lang, kind):
    lang = norm(lang)
    return T[lang]["kind"].get(kind, T["uz"]["kind"].get(kind, "REFERAT"))


def ai_directive(lang):
    return T[norm(lang)]["ai_directive"]
