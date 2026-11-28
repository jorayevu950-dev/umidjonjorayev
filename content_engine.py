# -*- coding: utf-8 -*-
"""
Mazmun generatori.

Bu modul mavzu nomini olib, tayyor tuzilma (reja, bo'limlar, matnlar) yaratadi.
Hech qanday tashqi API ishlatilmaydi - hammasi bepul va oflayn.
"""

import random
import re
import zlib

# ---------------------------------------------------------------------------
# 1. SOHA BO'YICHA LUG'ATLAR
# ---------------------------------------------------------------------------

DOMAINS = {
    "it": {
        "name": "axborot texnologiyalari",
        "keywords": [
            "axborot", "texnologiya", "kompyuter", "dastur", "internet", "intellekt",
            "raqamli", "kiber", "robot", "telefon", "dasturlash", "ma'lumotlar bazasi",
            "bulut", "sun'iy", "algoritm", "veb", "mobil ilova", "suniy", "it ", "ai",
        ],
        "concepts": [
            "raqamli transformatsiya jarayonlari",
            "axborot tizimlari va dasturiy yechimlar",
            "ma'lumotlarni qayta ishlash usullari",
            "foydalanuvchi tajribasi va interfeys dizayni",
            "kiberxavfsizlik va ma'lumotlar maxfiyligi",
            "sun'iy intellekt vositalari",
            "bulutli hisoblash xizmatlari",
            "tarmoq infratuzilmasi",
        ],
        "problems": [
            "Tizimlarning o'zaro integratsiyasi yetarli darajada ta'minlanmagan.",
            "Malakali mutaxassislar yetishmovchiligi loyihalarni reja bo'yicha yakunlashga to'sqinlik qiladi.",
            "Ma'lumotlar xavfsizligi bo'yicha amaliy choralar sust qolmoqda.",
            "Eskirgan infratuzilma yangi texnologiyalarni joriy etishni qiyinlashtiradi.",
            "Foydalanuvchilarning raqamli savodxonligi turlicha bo'lib, bu xizmatlardan foydalanishni cheklaydi.",
            "Litsenziyalangan dasturiy ta'minotdan foydalanish amaliyoti to'liq shakllanmagan.",
            "Loyihalarni baholash mezonlari aniq belgilanmaganligi samaradorlikni pasaytiradi.",
        ],
        "solutions": [
            "Kadrlarni muntazam malaka oshirish kurslari orqali tayyorlash maqsadga muvofiq.",
            "Yagona standartlar va ochiq interfeyslar asosida integratsiyani yo'lga qo'yish zarur.",
            "Xavfsizlik auditi va zaxira nusxalash tartibini joriy etish ijobiy natija beradi.",
            "Yangi yechimlarni pilot loyihalar orqali kichik miqyosda sinab ko'rish lozim.",
            "Foydalanuvchilar uchun qulay qo'llanmalar va texnik yordam xizmatini tashkil etish kerak.",
            "Ochiq kodli yechimlardan foydalanish xarajatlarni sezilarli kamaytirishi mumkin.",
            "Loyiha bosqichlarini aniq rejalashtirish va nazorat qilish amaliyotini kuchaytirish zarur.",
        ],
        "methods": [
            "Tadqiqotda qiyosiy tahlil usulidan foydalanildi.",
            "Amaliy natijalar kuzatuv va ekspert so'rovi asosida umumlashtirildi.",
            "Tizimli yondashuv orqali jarayonlar bosqichma-bosqich o'rganildi.",
            "Statistik ma'lumotlarni guruhlash usuli qo'llanildi.",
            "Nazariy xulosalar amaliy misollar bilan mustahkamlandi.",
            "Muammoli vaziyatlarni modellashtirish usuli qo'llanildi.",
        ],
        "trends": [
            "So'nggi yillarda raqamli xizmatlar hajmi izchil o'sib bormoqda.",
            "Sun'iy intellekt vositalari kundalik ish jarayonlariga tobora ko'proq kirib kelmoqda.",
            "Ma'lumotlarga asoslangan qarorlar qabul qilish amaliyoti kengaymoqda.",
            "Masofaviy ish va onlayn ta'lim shakllari ommalashmoqda.",
            "Kibxavfsizlikka oid talablar yildan-yilga kuchaymoqda.",
            "Milliy raqamli infratuzilmani rivojlantirishga alohida e'tibor qaratilmoqda.",
        ],
        "theses": [
            "Asosiy tushunchalar va atamalar",
            "Raqamli transformatsiya bosqichlari",
            "Amaliyotdagi asosiy qiyinchiliklar",
            "Kadrlar tayyorlash masalalari",
            "Xavfsizlik va maxfiylik talablari",
            "Xalqaro tajriba va standartlar",
            "Samaradorlik ko'rsatkichlari",
            "Kelgusi rivojlanish yo'nalishlari",
        ],
    },
    "iqtisod": {
        "name": "iqtisodiyot va moliya",
        "keywords": [
            "iqtisod", "bozor", "moliy", "bank", "soliq", "savdo", "investits",
            "tadbirkor", "byudjet", "narx", "valyuta", "kredit", "biznes", "marketing",
            "logistika", "eksport", "import", "bandlik", "inflyatsiya",
        ],
        "concepts": [
            "bozor mexanizmlari va raqobat muhiti",
            "moliyaviy resurslarni boshqarish usullari",
            "investitsiya muhiti va uning omillari",
            "narx shakllanishining iqtisodiy asoslari",
            "tadbirkorlik faoliyatini qo'llab-quvvatlash mexanizmlari",
            "soliq siyosatining iqtisodiyotga ta'siri",
            "bandlik va mehnat bozori holati",
        ],
        "problems": [
            "Moliyaviy resurslardan foydalanish samaradorligi yetarli darajada emas.",
            "Kichik biznes uchun kredit olish shartlari murakkabligicha qolmoqda.",
            "Raqobat muhitini shakllantirishda tizimli muammolar uchraydi.",
            "Investitsiyalarni jalb qilishda infratuzilma omili cheklovchi ta'sir ko'rsatadi.",
            "Moliyaviy savodxonlik darajasi aholining bir qismida past.",
            "Mahsulot tannarxini pasaytirish imkoniyatlari to'liq ishlatilmayapti.",
            "Statistik hisob-kitoblarning ishonchliligi bo'yicha ehtiyotkorlik talab etiladi.",
        ],
        "solutions": [
            "Moliyaviy rejalashtirish tizimini bosqichma-bosqich takomillashtirish zarur.",
            "Kichik biznes uchun imtiyozli kreditlash mexanizmlarini kengaytirish maqsadga muvofiq.",
            "Raqobat muhitini yaxshilash uchun ma'muriy to'siqlarni kamaytirish kerak.",
            "Investitsiya loyihalarini baholashda xatarlarni hisobga olish amaliyotini kuchaytirish lozim.",
            "Aholining moliyaviy savodxonligini oshirish bo'yicha tizimli ishlar talab etiladi.",
            "Xarajatlar tarkibini muntazam tahlil qilish orqali zaxiralarni aniqlash mumkin.",
        ],
        "methods": [
            "Tadqiqotda iqtisodiy ko'rsatkichlarni qiyosiy tahlil qilish usuli qo'llanildi.",
            "Ma'lumotlar dinamikasi asosida o'zgarish tendensiyalari aniqlandi.",
            "Ekspert baholash usuli orqali omillar ahamiyati saralandi.",
            "Guruhlash va tasniflash usullaridan foydalanildi.",
            "Nazariy xulosalar amaliy hisob-kitoblar bilan tekshirildi.",
        ],
        "trends": [
            "So'nggi yillarda xizmat ko'rsatish sohasining ulushi ortib bormoqda.",
            "Raqamli to'lov tizimlari kundalik amaliyotning ajralmas qismiga aylandi.",
            "Kichik va o'rta biznesni qo'llab-quvvatlash dasturlari kengaymoqda.",
            "Xalqaro savdoda yangi bozorlarga chiqish imkoniyatlari ko'paymoqda.",
            "Iqtisodiyotda resurs tejamkor texnologiyalarga talab kuchaymoqda.",
        ],
        "theses": [
            "Asosiy iqtisodiy tushunchalar",
            "Bozor mexanizmi va raqobat",
            "Moliyaviy resurslar tahlili",
            "Mavjud muammolar va sabablari",
            "Davlat siyosati va qo'llab-quvvatlash",
            "Xalqaro tajriba",
            "Samaradorlikni oshirish yo'llari",
            "Kelgusi istiqbollar",
        ],
    },
    "talim": {
        "name": "ta'lim va pedagogika",
        "keywords": [
            "ta'lim", "talim", "pedagog", "o'quv", "dars", "maktab", "universitet",
            "o'qituvchi", "oqituvchi", "student", "bilim", "metodika", "tarbiya",
            "sinf", "o'quvchi", "oquvchi", "kurs", "auditoriya", "malaka",
        ],
        "concepts": [
            "zamonaviy ta'lim texnologiyalari",
            "o'quv jarayonini tashkil etish shakllari",
            "bilimlarni baholash mezonlari",
            "interfaol o'qitish usullari",
            "pedagogik mahorat va uning tarkibiy qismlari",
            "o'quvchilarning motivatsiyasi",
            "individual yondashuv tamoyillari",
        ],
        "problems": [
            "O'quv jarayonida individual yondashuv imkoniyatlari cheklangan.",
            "Baholash tizimi ko'pincha faqat bilim hajmini o'lchash bilan cheklanadi.",
            "O'qituvchilarning malakasini oshirish imkoniyatlari notekis taqsimlangan.",
            "Zamonaviy texnologiyalardan foydalanish ko'nikmalari yetarli emas.",
            "O'quvchilarda mustaqil fikrlash ko'nikmasi sust shakllanmoqda.",
            "O'quv materiallarining amaliyot bilan bog'liqligi har doim ham ta'minlanmaydi.",
            "Ta'lim sifatini baholashning yagona mezonlari to'liq shakllanmagan.",
        ],
        "solutions": [
            "Darslarda interfaol va loyihaga asoslangan usullardan keng foydalanish zarur.",
            "Baholashda faqat natija emas, jarayon ham hisobga olinishi maqsadga muvofiq.",
            "O'qituvchilar uchun muntazam metodik seminarlar tashkil etish kerak.",
            "Raqamli resurslarni o'quv jarayoniga bosqichma-bosqich joriy etish lozim.",
            "O'quvchilarning mustaqil ishlarini tizimli rag'batlantirish talab etiladi.",
            "Nazariy bilimlarni amaliy mashg'ulotlar bilan mustahkamlash samara beradi.",
        ],
        "methods": [
            "Tadqiqotda pedagogik kuzatuv usulidan foydalanildi.",
            "So'rovnoma natijalari asosida o'quvchilar fikri o'rganildi.",
            "Tajriba-sinov ishlari orqali taklif etilgan usul samarasi baholandi.",
            "Ilg'or pedagogik tajribalar qiyosiy o'rganildi.",
            "Nazariy tahlil amaliy mashg'ulot natijalari bilan uyg'unlashtirildi.",
        ],
        "trends": [
            "So'nggi yillarda ta'limda raqamli platformalardan foydalanish kengaymoqda.",
            "Amaliy ko'nikmalarga yo'naltirilgan o'qitish usullari ommalashmoqda.",
            "Ta'lim jarayonini individuallashtirishga talab ortib bormoqda.",
            "Xalqaro baholash dasturlari tajribasi faol o'rganilmoqda.",
            "Uzluksiz ta'lim g'oyasi amaliyotda tobora mustahkamlanmoqda.",
        ],
        "theses": [
            "Mavzuning nazariy asoslari",
            "Zamonaviy ta'lim yondashuvlari",
            "O'quv jarayonini tashkil etish",
            "Amaliyotdagi muammolar",
            "Baholash mezonlari",
            "Xalqaro tajriba",
            "Amaliy xulosa",
            "Kutilayotgan natijalar",
        ],
    },
    "tibbiyot": {
        "name": "tibbiyot va sog'liqni saqlash",
        "keywords": [
            "tibbiyot", "sog'liq", "kasallik", "davolash", "shifokor", "bemor",
            "tibbiy", "vaktsina", "immunitet", "klinika", "dorixona", "diagnostika",
            "profilaktika", "salomatlik", "hamshira",
        ],
        "concepts": [
            "kasalliklarning oldini olish choralari",
            "zamonaviy diagnostika usullari",
            "davolash protokollari va standartlari",
            "bemorlar bilan muloqot madaniyati",
            "sog'lom turmush tarzi omillari",
            "tibbiy yordam sifatini baholash mezonlari",
            "profilaktik tekshiruvlarning ahamiyati",
        ],
        "problems": [
            "Aholining bir qismi profilaktik tekshiruvlardan o'z vaqtida o'tmaydi.",
            "Tibbiy yordamdan foydalanish imkoniyatlari hududlar bo'yicha farqlanadi.",
            "Kasalliklarni erta aniqlash amaliyoti to'liq yo'lga qo'yilmagan.",
            "Tibbiy xodimlarning malakasini oshirish imkoniyatlari cheklangan.",
            "Sog'lom turmush tarzi bo'yicha targ'ibot ishlari yetarli emas.",
            "Zamonaviy uskunalardan foydalanish ko'nikmalari har doim ham shakllanmagan.",
        ],
        "solutions": [
            "Profilaktik tekshiruvlarni keng omma uchun qulay qilish zarur.",
            "Birlamchi tibbiy yordam tizimini mustahkamlash maqsadga muvofiq.",
            "Tibbiy xodimlar uchun muntazam malaka oshirish kurslarini tashkil etish kerak.",
            "Aholi o'rtasida sog'lom turmush tarzi bo'yicha targ'ibotni kuchaytirish lozim.",
            "Zamonaviy diagnostika usullarini bosqichma-bosqich joriy etish talab etiladi.",
            "Bemorlar bilan ishlashda tushunarli tushuntirish amaliyotini rivojlantirish kerak.",
        ],
        "methods": [
            "Tadqiqotda klinik kuzatuv natijalari tahlil qilindi.",
            "Statistik ma'lumotlar asosida kasallanish tendensiyalari o'rganildi.",
            "Qiyosiy tahlil usuli orqali yondashuvlar solishtirildi.",
            "Adabiyotlar sharhi orqali nazariy asos yaratildi.",
            "Amaliy tavsiyalar ekspert xulosalari asosida shakllantirildi.",
        ],
        "trends": [
            "So'nggi yillarda profilaktikaga e'tibor kuchaymoqda.",
            "Raqamli tibbiyot xizmatlari rivojlanmoqda.",
            "Aholining sog'lom turmush tarziga qiziqishi ortib bormoqda.",
            "Masofaviy maslahat xizmatlari keng tarqalmoqda.",
            "Tibbiyotda xalqaro standartlarga o'tish jarayoni davom etmoqda.",
        ],
        "theses": [
            "Mavzuning tibbiy ahamiyati",
            "Asosiy tushunchalar",
            "Zamonaviy yondashuvlar",
            "Amaliyotdagi muammolar",
            "Profilaktika choralari",
            "Xalqaro tajriba",
            "Amaliy xulosa",
            "Kutilayotgan natijalar",
        ],
    },
    "ekologiya": {
        "name": "ekologiya va atrof-muhit",
        "keywords": [
            "ekolog", "atrof-muhit", "tabiat", "suv", "havo", "chiqindi", "ifloslanish",
            "iqlim", "o'rmon", "biologik", "tuproq", "resurs", "energiya", "quyosh",
        ],
        "concepts": [
            "atrof-muhitni muhofaza qilish choralari",
            "tabiiy resurslardan oqilona foydalanish tamoyillari",
            "chiqindilarni qayta ishlash yondashuvlari",
            "ekologik monitoring tizimi",
            "yashil iqtisodiyot tamoyillari",
            "iqlim o'zgarishiga moslashuv masalalari",
            "ekologik ta'lim va tarbiya",
        ],
        "problems": [
            "Chiqindilarni saralash va qayta ishlash amaliyoti yetarli darajada rivojlanmagan.",
            "Suv resurslaridan foydalanishda tejash texnologiyalari kam qo'llaniladi.",
            "Atmosfera havosi sifatini nazorat qilish tizimi to'liq qamrab olmagan.",
            "Ekologik qonunchilik talablariga rioya qilish nazorati sust.",
            "Aholining ekologik madaniyati yetarli darajada shakllanmagan.",
            "Sanoat korxonalarida resurs tejamkor texnologiyalar sekin joriy etilmoqda.",
        ],
        "solutions": [
            "Chiqindilarni saralash tizimini bosqichma-bosqich joriy etish zarur.",
            "Resurs tejamkor texnologiyalarni rag'batlantirish mexanizmlarini yaratish kerak.",
            "Ekologik monitoring tizimini raqamlashtirish samaradorlikni oshiradi.",
            "Aholi o'rtasida ekologik targ'ibot ishlarini kuchaytirish lozim.",
            "Qayta tiklanuvchi energiya manbalaridan foydalanishni kengaytirish maqsadga muvofiq.",
            "Korxonalarda ekologik audit o'tkazish amaliyotini yo'lga qo'yish talab etiladi.",
        ],
        "methods": [
            "Tadqiqotda kuzatuv va qiyosiy tahlil usullaridan foydalanildi.",
            "Statistik ma'lumotlar asosida tendensiyalar aniqlandi.",
            "Ekspert baholash usuli qo'llanildi.",
            "Amaliy misollar tahlili asosida xulosalar shakllantirildi.",
            "Normativ hujjatlar tahlil qilindi.",
        ],
        "trends": [
            "So'nggi yillarda ekologik masalalarga e'tibor sezilarli kuchaydi.",
            "Yashil texnologiyalarga investitsiyalar ortib bormoqda.",
            "Qayta tiklanuvchi energiya manbalaridan foydalanish kengaymoqda.",
            "Xalqaro ekologik talablar qat'iylashmoqda.",
            "Aholining ekologik ongi bosqichma-bosqich oshib bormoqda.",
        ],
        "theses": [
            "Mavzuning ekologik ahamiyati",
            "Asosiy tushunchalar",
            "Hozirgi holat tahlili",
            "Asosiy muammolar",
            "Muhofaza choralari",
            "Xalqaro tajriba",
            "Amaliy xulosa",
            "Kelgusi istiqbollar",
        ],
    },
    "huquq": {
        "name": "huquq va qonunchilik",
        "keywords": [
            "huquq", "qonun", "sud", "jinoyat", "fuqaro", "konstitutsiya", "javobgarlik",
            "shartnoma", "advokat", "prokuror", "mulk", "sudlov", "huquqbuzarlik", "nizо",
        ],
        "concepts": [
            "huquqiy munosabatlarning tarkibiy qismlari",
            "qonunchilik normalarining amal qilish mexanizmi",
            "fuqarolarning huquq va majburiyatlari",
            "huquqbuzarlik uchun javobgarlik asoslari",
            "sudlov amaliyoti va uning tahlili",
            "huquqiy madaniyat va huquqiy ong",
        ],
        "problems": [
            "Aholining huquqiy savodxonligi yetarli darajada emas.",
            "Normativ hujjatlar o'rtasida ziddiyatlar uchrab turadi.",
            "Sud qarorlarini ijro etish jarayonida qiyinchiliklar mavjud.",
            "Fuqarolarning o'z huquqlarini himoya qilish ko'nikmalari sust.",
            "Huquqni qo'llash amaliyotida turlicha talqinlar kuzatiladi.",
            "Yuridik yordamdan foydalanish imkoniyatlari hududlar bo'yicha farqlanadi.",
        ],
        "solutions": [
            "Huquqiy targ'ibot va tarbiya ishlarini tizimli yo'lga qo'yish zarur.",
            "Normativ hujjatlarni muntazam inventarizatsiya qilish amaliyotini joriy etish kerak.",
            "Sud qarorlari ijrosini nazorat qilish mexanizmlarini kuchaytirish lozim.",
            "Bepul yuridik maslahat xizmatlarini kengaytirish maqsadga muvofiq.",
            "Huquqni qo'llash bo'yicha yagona metodik tavsiyalar ishlab chiqish talab etiladi.",
        ],
        "methods": [
            "Tadqiqotda normativ hujjatlarni tahlil qilish usuli qo'llanildi.",
            "Sud amaliyoti materiallari o'rganildi.",
            "Qiyosiy-huquqiy tahlil usulidan foydalanildi.",
            "Nazariy xulosalar amaliy misollar bilan asoslandi.",
        ],
        "trends": [
            "So'nggi yillarda qonunchilik tizimi izchil yangilanmoqda.",
            "Raqamli huquq va ma'lumotlarni himoya qilish masalalari dolzarblashmoqda.",
            "Sud tizimini raqamlashtirish jarayoni davom etmoqda.",
            "Xalqaro huquqiy standartlarga yaqinlashish kuzatilmoqda.",
        ],
        "theses": [
            "Mavzuning huquqiy asoslari",
            "Asosiy tushunchalar",
            "Normativ baza tahlili",
            "Amaliyotdagi muammolar",
            "Sud va huquqni qo'llash amaliyoti",
            "Xalqaro tajriba",
            "Amaliy xulosa",
        ],
    },
    "qurilish": {
        "name": "qurilish va transport",
        "keywords": [
            "qurilish", "yo'l", "bino", "inshoot", "arxitektura", "beton", "material",
            "ko'prik", "loyiha", "transport", "avtomobil", "yol", "infratuzilma",
            "qurilish materiallari", "seysmik",
        ],
        "concepts": [
            "qurilish materiallari va ularning xossalari",
            "loyihalash bosqichidagi texnik talablar",
            "qurilish-montaj ishlarini tashkil etish",
            "sifat nazorati va me'yoriy hujjatlar",
            "xavfsizlik texnikasi talablari",
            "zamonaviy texnologiyalar va uskunalar",
            "inshootlarning mustahkamligi va chidamliligi",
        ],
        "problems": [
            "Materiallar sifatini nazorat qilish amaliyoti izchil emas.",
            "Loyiha hujjatlaridagi xatolar qurilish jarayonida qo'shimcha xarajat keltiradi.",
            "Malakali ishchi kuchiga bo'lgan talab to'liq qondirilmayapti.",
            "Muddatlarning buzilishi obyektlarni topshirishni kechiktirmoqda.",
            "Zamonaviy texnologiyalarni joriy etish sekin kechmoqda.",
            "Xavfsizlik talablariga rioya qilishda kamchiliklar uchraydi.",
        ],
        "solutions": [
            "Kiruvchi materiallar sifatini laboratoriya nazoratidan o'tkazish zarur.",
            "Loyiha hujjatlarini ekspertizadan o'tkazish amaliyotini kuchaytirish kerak.",
            "Ishchilar malakasini muntazam oshirish tizimini yo'lga qo'yish lozim.",
            "Ish grafigini aniq rejalashtirish va nazorat qilish samara beradi.",
            "Zamonaviy texnologiyalarni bosqichma-bosqich joriy etish maqsadga muvofiq.",
            "Xavfsizlik bo'yicha ko'rsatmalarni muntazam yangilab borish talab etiladi.",
        ],
        "methods": [
            "Tadqiqotda texnik hujjatlar tahlili usuli qo'llanildi.",
            "Obyektlardagi kuzatuv natijalari umumlashtirildi.",
            "Qiyosiy tahlil orqali yechimlar solishtirildi.",
            "Me'yoriy hujjatlar talablari o'rganildi.",
        ],
        "trends": [
            "So'nggi yillarda qurilish sohasida raqamli loyihalash kengaymoqda.",
            "Energiya tejamkor materiallarga talab ortib bormoqda.",
            "Infratuzilma loyihalariga investitsiyalar ko'paymoqda.",
            "Ekologik talablar qurilish jarayoniga tobora ko'proq ta'sir qilmoqda.",
        ],
        "theses": [
            "Mavzuning texnik asoslari",
            "Asosiy tushunchalar va me'yorlar",
            "Loyihalash bosqichlari",
            "Amaliyotdagi muammolar",
            "Sifat nazorati",
            "Zamonaviy texnologiyalar",
            "Amaliy xulosa",
        ],
    },
    "tarix": {
        "name": "tarix va madaniy meros",
        "keywords": [
            "tarix", "madaniyat", "meros", "qadim", "bobokalon", "davlat", "imperiya",
            "somoniy", "temur", "xalq", "urf-odat", "an'ana", "yodgorlik", "muzey",
        ],
        "concepts": [
            "tarixiy manbalar va ularning turlari",
            "madaniy meros obyektlari",
            "an'ana va urf-odatlarning uzviyligi",
            "tarixiy jarayonlarni davrlashtirish",
            "milliy o'zlikni anglash masalalari",
            "tarixshunoslikdagi yondashuvlar",
        ],
        "problems": [
            "Tarixiy manbalarning bir qismi hali to'liq o'rganilmagan.",
            "Madaniy meros obyektlarini asrash ishlari izchil olib borilmayapti.",
            "Tarixiy ma'lumotlarni talqin qilishda biryoqlamalik uchraydi.",
            "Yoshlarda tarixiy xotira yetarli darajada shakllanmagan.",
            "Ilmiy tadqiqotlarda arxiv materiallaridan foydalanish cheklangan.",
        ],
        "solutions": [
            "Arxiv materiallarini ilmiy muomalaga kiritish ishlarini kuchaytirish zarur.",
            "Madaniy meros obyektlarini muhofaza qilish tizimini takomillashtirish kerak.",
            "Tarixiy mavzularda ilmiy-ommabop nashrlar sonini ko'paytirish lozim.",
            "Ta'lim muassasalarida tarixiy tarbiya ishlarini kuchaytirish maqsadga muvofiq.",
            "Manbalarni qiyosiy o'rganish amaliyotini rivojlantirish talab etiladi.",
        ],
        "methods": [
            "Tadqiqotda tarixiy-qiyosiy usul qo'llanildi.",
            "Arxiv hujjatlari va ilmiy adabiyotlar tahlil qilindi.",
            "Manbashunoslik tahlili asosida xulosalar shakllantirildi.",
            "Tarixiy voqealarning o'zaro bog'liqligi o'rganildi.",
        ],
        "trends": [
            "So'nggi yillarda tarixiy merosni o'rganishga qiziqish ortmoqda.",
            "Madaniy meros obyektlarini restavratsiya qilish ishlari kengaymoqda.",
            "Raqamli arxivlar va elektron kutubxonalar rivojlanmoqda.",
            "Xalqaro ilmiy hamkorlik imkoniyatlari kengaymoqda.",
        ],
        "theses": [
            "Mavzuning tarixiy ildizlari",
            "Asosiy tushunchalar",
            "Tarixiy bosqichlar",
            "Manbalar tahlili",
            "Bugungi kun bilan bog'liqligi",
            "Xalqaro tajriba",
            "Xulosa va tavsiyalar",
        ],
    },
    "umumiy": {
        "name": "mavzu",
        "keywords": [],
        "concepts": [
            "asosiy tushunchalar va ta'riflar",
            "nazariy yondashuvlar",
            "amaliy jihatlar",
            "rivojlanish bosqichlari",
            "samaradorlik mezonlari",
            "zamonaviy talqinlar",
        ],
        "problems": [
            "Mavzu bo'yicha yagona yondashuv shakllanmagan.",
            "Amaliyotda nazariy bilimlarni qo'llashda qiyinchiliklar uchraydi.",
            "Resurslar cheklanganligi masalani to'liq hal etishga to'sqinlik qiladi.",
            "Masala bo'yicha statistik ma'lumotlar to'liq emas.",
            "Mutaxassislar o'rtasida turlicha fikrlar mavjud.",
        ],
        "solutions": [
            "Tizimli yondashuv asosida masalani bosqichma-bosqich hal etish zarur.",
            "Ilg'or tajribalarni o'rganish va qo'llash maqsadga muvofiq.",
            "Manbalar bazasini kengaytirish va yangilab borish kerak.",
            "Amaliy tavsiyalarni ishlab chiqish va sinovdan o'tkazish lozim.",
            "Mas'uliyatni aniq taqsimlash samaradorlikni oshiradi.",
        ],
        "methods": [
            "Tadqiqotda qiyosiy tahlil usulidan foydalanildi.",
            "Nazariy manbalar o'rganildi va umumlashtirildi.",
            "Amaliy misollar tahlil qilindi.",
            "Tizimli yondashuv qo'llanildi.",
        ],
        "trends": [
            "So'nggi yillarda mavzuga oid tadqiqotlar soni ortib bormoqda.",
            "Amaliyotda yangi yondashuvlar joriy etilmoqda.",
            "Xalqaro tajribaga qiziqish kuchaymoqda.",
        ],
        "theses": [
            "Mavzuning nazariy asoslari",
            "Asosiy tushunchalar",
            "Hozirgi holat tahlili",
            "Mavjud muammolar",
            "Yechim yo'llari",
            "Xalqaro tajriba",
            "Xulosa va takliflar",
        ],
    },
}


def detect_domain(topic: str) -> dict:
    """Mavzu nomidan sohani aniqlaydi."""
    text = " " + topic.lower().replace("‘", "'").replace("’", "'") + " "
    best, best_score = DOMAINS["umumiy"], 0
    for key, data in DOMAINS.items():
        score = sum(1 for kw in data["keywords"] if kw.strip() and kw in text)
        if score > best_score:
            best, best_score = data, score
    return best


# ---------------------------------------------------------------------------
# 2. GAP QOLIPLARI (har qanday mavzuga mos keladigan ilmiy jumlalar)
# ---------------------------------------------------------------------------

TEMPLATES = {
    "def": [
        "«{t}» masalasi bugungi kunda nazariy va amaliy ahamiyatga ega yo'nalishlardan biri sanaladi.",
        "Mazkur mavzu bo'yicha turli manbalarda turlicha yondashuvlar mavjud bo'lib, yagona talqin shakllanmagan.",
        "Mavzuning mazmunini ochishda uning nazariy asoslari va amaliy ko'rinishlarini birgalikda ko'rib chiqish talab etiladi.",
        "Tadqiqot doirasida mavzuga oid asosiy tushunchalar, jarayonlar va ularning o'zaro bog'liqligi tahlil qilinadi.",
    ],
    "importance": [
        "Mavzuning dolzarbligi shundan iboratki, u kundalik amaliyot bilan bevosita bog'liq.",
        "Masalaning dolzarbligi jamiyat hayotidagi o'zgarishlar bilan yanada kuchaymoqda.",
        "Ushbu yo'nalish bo'yicha bilim va ko'nikmalarga talab yildan-yilga ortib bormoqda.",
        "Mavzuni o'rganish amaliyotdagi muammolarni aniqlash va ularga yechim topishga xizmat qiladi.",
    ],
    "analysis": [
        "Tahlil jarayonida mavjud holat, uning sabablari va oqibatlari ketma-ket ko'rib chiqildi.",
        "Olingan ma'lumotlar asosida asosiy tendensiyalar va ularning o'zaro aloqasi aniqlandi.",
        "Mavjud yondashuvlarni qiyoslash orqali kuchli va kuchsiz tomonlar belgilandi.",
        "Tahlil natijalari mavzuning amaliy ahamiyatini yana bir bor tasdiqladi.",
    ],
    "problem": [
        "Shu bilan birga, mavzu doirasida bir qator hal etilmagan masalalar saqlanib qolmoqda.",
        "Mavjud kamchiliklarning asosiy sababi tizimli yondashuvning yetishmasligi bilan bog'liq.",
        "Amaliyotda uchraydigan qiyinchiliklar masalaning kompleks xarakterini ko'rsatadi.",
        "Ushbu muammolar o'z vaqtida hal etilmasa, kutilgan natijaga erishish qiyinlashadi.",
    ],
    "method": [
        "Tadqiqot metodologiyasi tizimli yondashuv, tahlil va umumlashtirish usullariga asoslanadi.",
        "Ish jarayonida nazariy manbalar va amaliy materiallar birgalikda o'rganildi.",
        "Olingan natijalar asosida asosli xulosalar shakllantirildi.",
        "Tadqiqotning ishonchliligini ta'minlash uchun bir nechta usullardan foydalanildi.",
    ],
    "solution": [
        "Yuqoridagi muammolarni hal etish uchun bosqichma-bosqich choralar ko'rish maqsadga muvofiq.",
        "Taklif etilayotgan yondashuv mavjud resurslar bilan mos kelishi bilan ajralib turadi.",
        "Amaliyotga joriy etish jarayonida natijalarni muntazam kuzatib borish zarur.",
        "Samaradorlikni baholash uchun aniq mezonlar belgilash talab etiladi.",
    ],
    "foreign": [
        "Xalqaro tajriba shuni ko'rsatadiki, mavzuga tizimli yondashuv ijobiy natija beradi.",
        "Rivojlangan davlatlar amaliyotida bu yo'nalishda samarali mexanizmlar shakllangan.",
        "Ilg'or tajribalarni milliy sharoitga moslashtirib qo'llash mumkin.",
        "Xalqaro standartlar talablarini hisobga olish natijalarning ishonchliligini oshiradi.",
    ],
    "conclusion": [
        "O'tkazilgan tahlil mavzuning amaliy ahamiyatini tasdiqladi.",
        "Mavjud muammolarni hal etish uchun tizimli va izchil yondashuv zarur.",
        "Taklif etilgan choralar amaliyotga joriy etilsa, ijobiy natijalarga erishish mumkin.",
        "Mavzu bo'yicha keyingi tadqiqotlar uchun bir qator yo'nalishlar ochiq qolmoqda.",
    ],
}

CONCEPT_FRAMES = [
    "Mavzu doirasida {c} masalasiga alohida e'tibor qaratildi.",
    "Tahlil jarayonida {c} bilan bog'liq jihatlar o'rganildi.",
    "{c} mavzuning mazmunini ochishda muhim o'rin tutadi.",
    "Shu bilan birga, {c} bo'yicha mavjud amaliyot umumlashtirildi.",
    "{c} alohida ko'rib chiqilishi lozim bo'lgan jihatlardan biri sanaladi.",
    "Ishning amaliy qismida {c} tahlil markazida bo'ldi.",
    "{c} masalasiga oid yondashuvlar o'zaro qiyoslandi.",
    "{c} bo'yicha mavjud holat baholandi va xulosalar shakllantirildi.",
]

PAIR_FRAMES = [
    "{c1} va {c2} o'rtasidagi o'zaro bog'liqlik alohida o'rganildi.",
    "{c1} bilan birga {c2} ham mavzuning muhim tarkibiy qismi sifatida ko'rib chiqildi.",
    "{c1} tajribasi {c2} bo'yicha amaliy xulosalar chiqarishga asos bo'ldi.",
    "Tahlil jarayonida {c1} va {c2} bo'yicha mavjud ma'lumotlar qiyoslandi.",
    "{c1} va {c2} bir-biri bilan chambarchas bog'liq bo'lib, ularni alohida ko'rib chiqish qiyin.",
    "Mavzu doirasida {c1} masalasi {c2} bilan uzviy aloqada tahlil qilindi.",
]

CONNECTORS = [
    ("Shu bilan birga, ", "shu bilan birga, "),
    ("Bundan tashqari, ", "bundan tashqari, "),
    ("Ta'kidlash joizki, ", "ta'kidlash joizki, "),
    ("Shu nuqtai nazardan, ", "shu nuqtai nazardan, "),
]

CHAPTERS_DEFAULT = [
    (
        "Mavzuning nazariy asoslari",
        ["Asosiy tushunchalar va ta'riflar", "Mavzuning o'rganilganlik darajasi"],
    ),
    (
        "Amaliy holat tahlili",
        ["Hozirgi holat va rivojlanish tendensiyalari", "Muammolar va ularning sabablari"],
    ),
    (
        "Natijalar va istiqbollar",
        ["Yechim yo'llari", "Samaradorlikni oshirish istiqbollari"],
    ),
]

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]


def _clean_topic(topic: str) -> str:
    topic = topic.strip().replace("\n", " ")
    topic = re.sub(r"\s+", " ", topic)
    topic = topic.rstrip(".;")
    return topic


def _cap(s: str) -> str:
    s = s.strip()
    return s[0].upper() + s[1:] if s else s

def _low(s: str) -> str:
    s = s.strip()
    return s[0].lower() + s[1:] if s else s


def _add_connector(sentence: str, rnd: random.Random) -> str:
    up, low = rnd.choice(CONNECTORS)
    if sentence[:1].isupper():
        return up + _low(sentence)
    return sentence


OPENERS = [
    "Amaliyot shuni ko'rsatadiki, ",
    "Tahlil natijalari bo'yicha, ",
    "Kuzatuvlar asosida shuni aytish mumkin: ",
    "Ekspertlar fikriga ko'ra, ",
    "Mavjud manbalar tahliliga tayanib aytish mumkin-ki, ",
    "O'rganilgan materiallar asosida, ",
    "Mavzu bo'yicha olib borilgan ishlar doirasida, ",
    "Nazariy manbalarni umumlashtirib aytadigan bo'lsak, ",
]


def _fresh_template(rnd, used, role, topic):
    pool = TEMPLATES.get(role, TEMPLATES["analysis"])
    for _ in range(24):
        s = rnd.choice(pool).replace("{t}", topic)
        if s not in used:
            used.add(s)
            return s
    return None


def _fresh_concept(rnd, used, domain):
    for _ in range(30):
        s = rnd.choice(CONCEPT_FRAMES).replace("{c}", rnd.choice(domain["concepts"]))
        if s not in used:
            used.add(s)
            return s
    return None


def _fresh_pair(rnd, used, domain):
    if len(domain["concepts"]) < 2:
        return None
    for _ in range(30):
        c1, c2 = rnd.sample(domain["concepts"], 2)
        if " va " in c1 or " va " in c2:
            continue
        s = rnd.choice(PAIR_FRAMES).replace("{c1}", c1).replace("{c2}", c2)
        if s not in used:
            used.add(s)
            return s
    return None


def _fresh_item(rnd, used, pool, op_used=None, style=True):
    """Ro'yxatdan jumla oladi, kirish so'zi bilan variant yasaydi."""
    if not pool:
        return None
    for _ in range(40):
        base = rnd.choice(pool)
        if style and rnd.random() < 0.5:
            choices = [o for o in OPENERS if not op_used or o not in op_used] or OPENERS
            op = rnd.choice(choices)
            s = op + base[0].lower() + base[1:]
            if op_used is not None:
                op_used.add(op)
        else:
            s = base
        if s not in used:
            used.add(s)
            return s
    return None


def _finalize(sentences):
    """Bosh harf, nuqta va ortiqcha bo'shliqlarni tartibga soladi."""
    out = []
    for s in sentences:
        if not s:
            continue
        s = " ".join(s.split())
        s = s[0].upper() + s[1:]
        if not s.endswith((".", "!", "?")):
            s += "."
        out.append(s)
    return " ".join(out)


def make_paragraph(rnd, used, role, topic, domain, sentences=5):
    """Bitta mantiqiy paragraf yig'adi (takrorlanishsiz)."""
    parts = []
    t = _fresh_template(rnd, used, role, topic)
    if t:
        parts.append(t)

    c = _fresh_concept(rnd, used, domain)
    if c:
        parts.append(c)

    p = _fresh_pair(rnd, used, domain)
    if p:
        parts.append(p)

    groups = {
        "def": "theory",
        "importance": "theory",
        "method": "method",
        "analysis": "problem",
        "problem": "problem",
        "foreign": "problem",
        "solution": "solution",
        "conclusion": "solution",
    }
    group = groups.get(role, "theory")
    op_used = set()

    first_pool = {
        "problem": domain["problems"],
        "analysis": domain["problems"],
        "solution": domain["solutions"],
        "conclusion": domain["solutions"],
        "importance": domain["trends"],
        "foreign": domain["trends"],
        "method": domain["methods"],
        "def": domain["trends"],
    }.get(role, domain["trends"])
    it = _fresh_item(rnd, used, first_pool, op_used)
    if it:
        parts.append(it)

    fill_by_group = {
        "theory": [domain["trends"], domain["concepts"], domain["methods"]],
        "problem": [domain["problems"], domain["trends"], domain["concepts"]],
        "solution": [domain["solutions"], domain["concepts"], domain["methods"]],
        "method": [domain["methods"], domain["concepts"], domain["trends"]],
    }
    fill_pools = fill_by_group[group]
    k = 0
    while len(parts) < sentences and k < 20:
        pool = fill_pools[k % len(fill_pools)]
        k += 1
        if pool is domain["concepts"]:
            item = _fresh_concept(rnd, used, domain)
        else:
            item = _fresh_item(rnd, used, pool, op_used)
        if item:
            parts.append(item)

    # ba'zi jumlalarga bog'lovchi so'z qo'shish
    for i in range(1, len(parts)):
        if rnd.random() < 0.22:
            if any(parts[i].startswith(op) for op in OPENERS):
                continue
            parts[i] = _add_connector(parts[i], rnd)

    return _finalize(parts)


# ---------------------------------------------------------------------------
# 3. REFERAT / MUSTAQIL ISH TUZILMASI
# ---------------------------------------------------------------------------

REFERENCES = [
    "O'zbekiston Respublikasi Prezidentining rasmiy veb-sayti: www.president.uz",
    "O'zbekiston Milliy kutubxonasi elektron katalogi: www.natlib.uz",
    "O'zbekiston Respublikasi Qonun hujjatlari milliy bazasi: lex.uz",
    "Google Scholar ilmiy qidiruv tizimi: scholar.google.com",
    "CyberLeninka ilmiy elektron kutubxonasi: cyberleninka.ru",
    "ZiyoNET ta'lim portali: ziyonet.uz",
]


def _chapters_from_plan(plan):
    """Foydalanuvchi bergan reja asosida bo'limlar tuzadi."""
    chapters = []
    for i, title in enumerate(plan[:5]):
        clean = re.sub(r"^[\d\s.\-)]+", "", title).strip()
        clean = _cap(clean)
        subs = [
            "Asosiy tushunchalar va yondashuvlar",
            "Tahlil va amaliy natijalar",
        ]
        chapters.append((clean, subs))
    return chapters


def build_document(topic, info, pages=10, plan=None, kind="referat"):
    """Referat yoki mustaqil ish uchun tuzilma va matnlarni yaratadi."""
    topic = _clean_topic(topic)
    domain = detect_domain(topic)
    # Bir xil mavzu uchun matn har doim bir xil bo'lishi uchun
    # barqaror (o'zgarmas) urug' ishlatiladi
    rnd = random.Random(zlib.crc32(topic.encode("utf-8")))
    used = set()

    plan = [_cap(p) for p in (plan or []) if p.strip()]
    chapters_src = _chapters_from_plan(plan) if plan else CHAPTERS_DEFAULT

    total_subs = sum(len(s) for _, s in chapters_src)
    pages = max(6, min(30, int(pages)))
    # Kichik hajmlarda gaplar soni kamaytiriladi - shunda bet soni
    # so'ralgan hajmga yaqin chiqadi
    sent = 4 if pages <= 9 else 5
    # Betlar soni titul varaq, mundarija va boblar uchun ajratilgan
    # joyni hisobga olib, matn hajmiga aylantiriladi
    target_paras = max(12, int(round(pages * 4.7 - 8.0)))
    intro_count = 3 if pages < 14 else 4
    concl_count = 3 if pages < 14 else 4
    body_target = max(total_subs * 2, target_paras - intro_count - concl_count)
    base = body_target // total_subs
    extra = body_target % total_subs

    intro_roles = ["def", "importance", "method", "analysis"]
    intro = []
    for i in range(intro_count):
        role = intro_roles[i % len(intro_roles)]
        intro.append(make_paragraph(rnd, used, role, topic, domain, sentences=sent))

    chapters = []
    idx = 0
    for ci, (chapter_title, subs) in enumerate(chapters_src):
        ch = {
            "title": f"{ROMAN[ci]} BOB. {chapter_title.upper()}",
            "subs": [],
        }
        for si, sub_title in enumerate(subs):
            n_paras = base + (1 if idx < extra else 0)
            n_paras = max(2, n_paras)
            idx += 1
            if ci == 0:
                roles = ["def", "method", "importance", "analysis"]
            elif ci == 1:
                roles = ["analysis", "problem", "foreign", "analysis"]
            else:
                roles = ["solution", "method", "conclusion", "solution"]
            paras = []
            for pi in range(n_paras):
                role = roles[pi % len(roles)]
                if role == "concept":
                    role = "def"
                paras.append(make_paragraph(rnd, used, role, topic, domain, sentences=sent))
            ch["subs"].append({
                "title": f"{ci + 1}.{si + 1}. {_cap(sub_title)}",
                "paras": paras,
            })
        chapters.append(ch)

    conclusion = []
    for i in range(concl_count):
        role = ["conclusion", "solution", "conclusion"][i % 3]
        conclusion.append(make_paragraph(rnd, used, role, topic, domain, sentences=sent))

    refs = list(REFERENCES)
    if info.get("fan"):
        refs.append(f"{info['fan']} fani bo'yicha ma'ruza matnlari va o'quv qo'llanmalari.")
    refs.append(f"Internet manbalari: «{topic}» mavzusi bo'yicha elektron materiallar.")

    return {
        "kind": kind,
        "topic": topic,
        "info": info,
        "domain": domain["name"],
        "intro": intro,
        "chapters": chapters,
        "conclusion": conclusion,
        "references": refs,
    }


# ---------------------------------------------------------------------------
# 4. PREZENTATSIYA TUZILMASI
# ---------------------------------------------------------------------------

def _fresh_plain(rnd, used, pool, count):
    """Qisqa iboralar ro'yxatidan takrorlanmas variantlar oladi."""
    out = []
    if not pool:
        return out
    for _ in range(count):
        for _ in range(30):
            item = rnd.choice(pool)
            if item not in used:
                used.add(item)
                out.append(item)
                break
    return out


def _shorten(text, limit=88):
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut:
        cut = cut[:cut.rfind(" ")]
    return cut.rstrip(" ,.;:") + "..."


def _slide_bullet(rnd, used, pool, limit=95):
    """Slayd uchun qisqa jumla tanlaydi (uzunlari chetlab o'tiladi)."""
    if not pool:
        return None
    for _ in range(8):
        item = rnd.choice(pool)
        if item in used or len(item) > limit:
            continue
        used.add(item)
        return _cap(item)
    return None


def _slide_concept(rnd, used, domain, limit=95):
    item = _fresh_concept(rnd, used, domain)
    if not item:
        return None
    return _cap(_shorten(item, limit))


def _slide_template(rnd, used, role, topic, limit=95):
    item = _fresh_template(rnd, used, role, topic)
    if not item:
        return None
    return _cap(_shorten(item, limit))


def build_presentation(topic, info, slides=10, plan=None):
    """Prezentatsiya uchun slaydlar tuzilmasi."""
    topic = _clean_topic(topic)
    domain = detect_domain(topic)
    rnd = random.Random((hash(topic) + 7) & 0xFFFFFFFF)
    used = set()

    plan = [_cap(p) for p in (plan or []) if p.strip()]
    if not plan:
        plan = [c for c, _ in CHAPTERS_DEFAULT]

    slides = max(7, min(30, int(slides)))
    body_count = max(3, slides - 5)

    plan_slide = {"title": "Reja", "bullets": [_cap(p) for p in plan][:6]}

    titles_pool = list(dict.fromkeys(
        plan + [t for t in domain["theses"] if t not in plan]
    ))
    content_slides = []
    sent_pools = [domain["trends"], domain["problems"], domain["solutions"]]

    for i in range(body_count):
        title = titles_pool[i % len(titles_pool)]
        bullets = []
        tkey = title.lower()

        for c in _fresh_plain(rnd, used, domain["concepts"], 2):
            b = _cap(_shorten(c, 80))
            if b.lower() != tkey:
                bullets.append(b)

        pool = sent_pools[i % len(sent_pools)]
        tries = 0
        while len(bullets) < 5 and tries < 14:
            tries += 1
            source = sent_pools[tries % len(sent_pools)]
            b = _slide_bullet(rnd, used, source)
            if b and b.lower() != tkey and b not in bullets:
                bullets.append(b)
                continue
            for c in _fresh_plain(rnd, used, domain["concepts"], 1):
                b = _cap(c)
                if b.lower() != tkey and b not in bullets:
                    bullets.append(b)

        content_slides.append({"title": _cap(title), "bullets": bullets[:5]})

    conclusion_bullets = []
    pools_cycle = [domain["solutions"], domain["trends"], domain["problems"],
                   domain["solutions"], domain["trends"]]
    tries = 0
    while len(conclusion_bullets) < 5 and tries < 16:
        source = pools_cycle[tries % len(pools_cycle)]
        tries += 1
        b = _slide_bullet(rnd, used, source)
        if b and b not in conclusion_bullets:
            conclusion_bullets.append(b)
            continue
        b = _slide_template(rnd, used, "conclusion", topic)
        if b and b not in conclusion_bullets:
            conclusion_bullets.append(b)
            continue
        for c in _fresh_plain(rnd, used, domain["concepts"], 1):
            if c not in conclusion_bullets:
                conclusion_bullets.append(_cap(c))

    return {
        "kind": "prezentatsiya",
        "topic": topic,
        "info": info,
        "domain": domain["name"],
        "plan": plan,
        "plan_slide": plan_slide,
        "slides": content_slides,
        "conclusion": conclusion_bullets,
        "references": list(REFERENCES)[:5],
    }


if __name__ == "__main__":
    doc = build_document("Axborot texnologiyalarining ta'lim jarayonidagi o'rni", {"fish": "Karimov Ali", "fan": "Informatika"}, pages=10)
    words = sum(len(p.split()) for p in doc["intro"] + doc["conclusion"])
    for ch in doc["chapters"]:
        for s in ch["subs"]:
            words += sum(len(p.split()) for p in s["paras"])
    print("Soha:", doc["domain"], "| so'z:", words)
    print(doc["chapters"][0]["subs"][0]["paras"][0][:300])
    pres = build_presentation("Axborot texnologiyalarining ta'lim jarayonidagi o'rni", {}, slides=10)
    print("Slaydlar:", len(pres["slides"]) + 4)
    print(pres["slides"][0])
