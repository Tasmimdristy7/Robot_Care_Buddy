# Robot Care Buddy

A small Python/Django study planner with a floating illustrated robot that reminds you about exams and assignments in speech bubbles.

## Three major functionalities

1. **Task management:** create, edit, and delete exams and assignments with course names and timezone-aware deadlines, persisted in SQLite.
2. **Deadline reminders:** the robot floats into the app when a task is due within 48 hours or overdue; snooze for 15 minutes, dismiss for 30 minutes in the current page, or complete from the bubble. Checks run every 30 seconds and when you return to the tab.
3. **Progress tracking:** complete/reopen tasks, search by task or course, filter upcoming/overdue/completed tasks, and see workload and completion counts.

## Run locally

Python 3.10+ is required. This is a local, single-user application with no accounts.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8002
```

Open http://127.0.0.1:8002/. On Windows, activate with `.venv\Scripts\activate`.

Add an assignment with a deadline an hour from now to see a real reminder. “Meet your buddy” shows a sample greeting without creating a task. Snoozes survive reloads; dismissed reminders may return after reload. Tasks remain in the local `db.sqlite3` file, which is excluded from Git.

Dates are entered and displayed in the browser's timezone and sent as explicit UTC timestamps. Overdue tasks appear under Overdue or All. The Upcoming tab excludes completed and overdue tasks.

## Monthly calendar

Use the previous/next month arrows or Today, then select a day to see its exams and assignments in deadline order. The calendar includes completed tasks and is independent of the list filters and search below it. Dates and times use the browser’s timezone, including daylight saving changes.

Run calendar regression checks with `node --test tests/calendar.cjs` (Node.js 18+).

## Open-source reference

**Simply Todo App** by ptyadana: https://github.com/ptyadana/django-WEB-simple-todo

License: MIT. Its README describes a small Django app for adding and completing daily tasks. We used its documented functionality and small application scope as a reference, not its source code. No reference code, artwork, templates, or dependencies were copied.

| Reference functionality | Our independent implementation |
| --- | --- |
| Add tasks | Add assignments/exams with course and deadline |
| Complete tasks | Complete/reopen tasks and show progress |
| View daily to-do list | Searchable list with upcoming, overdue, and completed views |

Our deadline checks, snooze behavior, rounded robot artwork, and floating speech-bubble interface are original additions. Both projects remain small task-management applications; this is not a clone of a large planner platform.

## AI tool used

**OpenAI Codex** was used to generate the pytest tests for this assignment. The generated tests were reviewed and verified locally, including line coverage of the selected `reminders()` function.

## Validation

```sh
python manage.py check
python -m pip install -r requirements-dev.txt
python -m pytest
python -m pytest --cov=planner --cov-report=term-missing --cov-report=html --cov-report=json
python manage.py collectstatic --noinput
```

Tests cover CRUD, invalid input, reminder eligibility, snooze expiry, completion exclusion, timezone conversion, CSRF enforcement, and missing routes. Browser JavaScript handles animation and polling; Django handles validation, persistence, and reminder selection.

Python tests use pytest with pytest-django and pytest-cov. Open `htmlcov/index.html` to inspect line coverage. The assignment's selected function is `planner.views.reminders`; its coverage should be checked separately from the coverage of the entire module. JavaScript calendar regression checks use Node.js as described above.

## Scope

Reminders work inside the open application, not over other desktop apps or while closed. This version is intended for a single user on localhost; it has no access controls and should not be exposed publicly as a shared planner. GitHub hosts the source; a Django server is needed to run the application. No external AI service, email service, or paid API is required.

Future tasks are tracked in GitHub Issues and the assignment Project board.
