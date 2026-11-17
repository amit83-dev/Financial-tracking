# claude-fallback — המשך אוטומטי כשנגמרת המכסה

כשהמכסה של Claude Code נגמרת, נפתח **אוטומטית** חלון טרמינל חדש באותה תיקייה שממשיך את **אותה שיחה** (`claude --continue`) דרך ראוטר מקומי. הראוטר בוחר לכל בקשה את המודל המתאים למשימה, ואם ספק נכשל, עובר לבא אחריו.

## התקנה (פקודה אחת, על המחשב שלכם)
דרישות: Python 3.8+, Claude Code, ו-Node.js 20+ (רק בשביל Copilot).

```bash
git clone <כתובת הריפו> && cd Financial-tracking && git checkout claude/youthful-gauss-k2co1t
python3 claude-fallback/install.py        # בווינדוס: py claude-fallback\install.py
```
המתקין שואל: מפתח Gemini (חינמי: https://aistudio.google.com/apikey), האם להפעיל Copilot (התחברות ל-GitHub פעם אחת), ומפתחות אופציונליים ל-DeepSeek/OpenRouter. הוא:
1. מעתיק את הקבצים ל-`~/.claude-fallback`
2. שולף מכל ספק את רשימת המודלים האמיתית ובוחר את הטובים ביותר לכל סוג משימה
3. מוסיף hook ל-`~/.claude/settings.json` (נשמר גיבוי `.bak-claude-fallback`)
4. בודק שכל ספק עונה

אחרי ההתקנה: **פתחו חלון Claude Code חדש** כדי שיקרא את ה-hook. זהו.

## איך בוחרים מודל לפי משימה
| שכבה | מתי | סדר עדיפויות |
|---|---|---|
| background | קריאות רקע (Haiku, כותרות) | Gemini Flash-Lite ← Copilot קטן ← DeepSeek |
| simple | הסבר, שינוי שם, README, תיעוד | Gemini Flash ← Copilot ← DeepSeek |
| code | ברירת מחדל: כתיבה ותיקון קוד | Copilot Sonnet ← Gemini Pro ← DeepSeek |
| hard | תכנון, ארכיטקטורה, דיבוג, ריפקטור, thinking/plan | Gemini Pro ← Copilot ← DeepSeek |
| long | הקשר מעל ~120K טוקנים | Gemini Pro/Flash |
| vision | יש תמונה | Gemini ← Copilot |

- בתוך משימה אחת (המשך אחרי כלי) המודל נשאר קבוע, כדי שלא יתחלף באמצע.
- אפשר לכפות: פתחו הודעה ב-`!hard`, `!fast`, `!code` או `!gemini` / `!copilot` / `!deepseek`.
- לשינוי ידני ערכו `~/.claude-fallback/config.json` (השדה `tiers`; השינוי נקלט בלי הפעלה מחדש).

## שימוש ידני / פקודות
- `keepgoing` — מעבר ידני בטרמינל הנוכחי (הוסיפו `~/.claude-fallback/bin` ל-PATH).
- `python3 ~/.claude-fallback/router.py selftest` — בדיקת כל הספקים. `... models` — רשימת מודלים.
- כיבוי המעבר האוטומטי: `CLAUDE_FALLBACK_AUTO=0`. יומנים: `~/.claude-fallback/router.log`.
- כשהמכסה חוזרת, פשוט חזרו להשתמש ב-`claude` הרגיל. הוא לא השתנה.

## חשוב לדעת
- **פרטיות:** בזמן גיבוי הקוד נשלח ל-Google / GitHub Copilot / ספקים שהפעלתם. לקוד רגיש השאירו רק ספקים שאתם סומכים עליהם (כל ספק בלי מפתח כבוי).
- **Copilot** עובד דרך `copilot-api`, פרויקט לא רשמי שמבוסס על הנדסה לאחור. GitHub מזהירה ששימוש אוטומטי אינטנסיבי עלול להפעיל זיהוי ניצול ולהשעות זמנית את הגישה. מתאים לגיבוי, לא לעבודה רצופה.
- **חלון חדש:** החלון הישן נשאר פתוח. אל תכתבו בו, כדי ששני חלונות לא יעבדו על אותה שיחה. אם יש כמה שיחות באותה תיקייה, ממשיכה האחרונה.
- ה-hook מופעל לכל תיקייה פעם ב-30 דקות לכל היותר.
- הקוד נבדק בסביבת דמה (שרתי Gemini/Anthropic מזויפים: סטרימינג, כלים, failover, בחירת שכבה) ב-`python3 claude-fallback/test_router.py`, **לא מול ספקים אמיתיים**. שמות מודלים, חתימות מחשבה של Gemini ותאימות `copilot-api` יש לאמת עם `selftest` אחרי ההתקנה. אם ספק נכשל הראוטר פשוט עובר לבא אחריו.
