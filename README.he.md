# NESTRA — תקציר בעברית

**Nature-inspired Evidence Selection, Trust-aware Routing Architecture**

NESTRA היא שכבת הסקה וניתוב אדפטיבית בפייתון בין הלקוח לבין מערכות אחזור, זיכרון, ML ו־LLM. היא מחליטה מתי אין צורך במודל בכלל, מתי מספיקה קריאת Micro קצרה, ומתי חייבים להסלים ל־Meso או Full כדי לא לפגוע בדיוק.

```text
לקוח -> NESTRA -> חסימה | אחזור בלבד | Micro | Meso | Full -> בדיקת דיוק -> תשובה
```

NESTRA אינה אייג'נט ואינה framework לאייג'נטים. אפליקציה, API, מערכת RAG או אייג'נט יכולים להשתמש בה, אך אין צורך באייג'נט כדי להפעיל אותה. היא מפרידה בין Retrieval לבין Generation: בקשת מקורות או עובדות יכולה להסתיים עם אפס קריאות מודל ואפס טוקני ספק. כאשר כן נדרש LLM, כל מסלול מוגבל בתקציב ומוגן בבדיקות אמון, רגישות, prompt injection, מקורות, grounding ומבנה פלט.

## התחלה מהירה

הפרויקט כתוב בפייתון 3.10 ומעלה, ללא תלויות בזמן ריצה:

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python scripts\validate_release.py

nestra ingest --project casting --file examples\project-memory\casting.json --trust trusted
nestra query --project casting --question "Show the evidence sources" --mode retrieval
```

הפקודה האחרונה אינה דורשת מפתח API וצורכת אפס טוקני LLM. למסלולי generation מגדירים `OPENAI_API_KEY`. ברירות המחדל ממפות את התפקידים ל־GPT-5.6 Luna עבור Micro, Terra עבור Meso ו־Sol עבור Full, אך ממשק הספק ניתן להחלפה.

## הנתב הלומד

קיים מודל Logistic Regression מקומי ואופציונלי שמעריך מתי Micro עשוי להיות בטוח. הוא משתמש ב־15 מאפייני ניתוב מספריים, אינו צורך טוקנים ואינו שומר שאלות או ראיות גולמיות בקובץ המודל. חסימה, אחזור בלבד, אמון, רגישות, prompt injection ובדיקת התשובה נשארים דטרמיניסטיים ויכולים להטיל veto על המודל.

המודל המצורף מסומן `experimental` ואינו מופעל אוטומטית. מערך הכיול הקטן לא עמד בדרישת Micro precision של 0.90, ולכן Micro הושבת בו. זאת תשתית ML מלאה ושקופה — אימון, כיול, holdout, artifact, אינטגרציה וניטור — ולא טענה מוקדמת לחיסכון מוכח.

יעד 50–100 הטוקנים שייך למסלול Micro בלבד והוא עדיין היפותזה מחקרית. כישלון בבדיקת הדיוק גורם להסלמה או ל־`needs_review`; NESTRA אינה חוסכת טוקנים על חשבון תשובה לא מבוססת.

התיעוד המלא, ה־API, האבטחה, המדדים והניסויים נמצאים ב־[README הראשי](README.md).
