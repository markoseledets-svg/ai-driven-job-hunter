from email.message import EmailMessage

ALLOWED_TEST_EMAILS = frozenset(
    {
        "jobalerts-noreply@linkedin.com",
        "noreply@work.ua",
        "alerts@mailing.rabota.ua",
    }
)


def build_eml(sender: str, html: str | None, subject: str = "Job Alert") -> bytes:
    """Build a synthetic MIME email message as raw bytes for parser and IMAP tests."""
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "candidate@example.com"
    msg["Subject"] = subject
    msg.set_content("Plain text fallback")
    if html is not None:
        msg.add_alternative(html, subtype="html")
    return msg.as_bytes()


def linkedin_digest_eml() -> bytes:
    html = """
    <html><body>
      <a href="https://www.linkedin.com/comm/jobs/view/4432476345/?trackingId=abc&amp;refId=xyz">
        <img alt="Acme Corp" src="logo.png" />
      </a>
      <a href="https://www.linkedin.com/comm/jobs/view/4432476345/?trackingId=abc&amp;refId=xyz">
        <p>Back End Developer</p>
        <p>Acme Corp · EMEA (Віддалена робота)</p>
        <p>Проводиться активний набір персоналу</p>
      </a>
      <a href="https://www.linkedin.com/comm/jobs/view/4432476345/?trackingId=abc&amp;refId=xyz">
        Back End Developer
      </a>
      <a href="https://www.linkedin.com/comm/jobs/view/4343363446/?trackingId=def">
        <p>Python Engineer</p>
        <p>CloudLab · Lviv (Робота в офісі)</p>
      </a>
    </body></html>
    """
    return build_eml("LinkedIn <jobalerts-noreply@linkedin.com>", html)


def work_ua_digest_eml() -> bytes:
    html = """
    <html><body>
      <div>
        <a href="https://www.work.ua/jobs/8673772/?utm_source=email"></a>
        <a href="https://www.work.ua/jobs/8673772/?utm_source=email">Python developer</a>
        <p>
          <a href="https://www.work.ua/jobs/8673772/?utm_source=email">FinTech Corp</a>
          · Дистанційно
        </p>
      </div>
    </body></html>
    """
    return build_eml("Work.ua <noreply@work.ua>", html)


def work_ua_instant_eml() -> bytes:
    html = """
    <html><body>
      <p>Вакансія від 20.11.2026</p>
      <h1><a href="https://www.work.ua/jobs/8248191/?utm_source=instant">Junior Python Dev</a></h1>
      <p>40 000 – 55 000 грн</p>
      <p><a href="https://www.work.ua/jobs/by-company/12345/">NovaSoft</a></p>
      <p>Львів</p>
      <p>Контакт ·</p>
      <p>Показати телефон</p>
      <h2>Опис вакансії</h2>
      <p>Building FastAPI services and PostgreSQL migrations.</p>
      <p>Відгукнутися</p>
    </body></html>
    """
    return build_eml("Work.ua <noreply@work.ua>", html)


def robota_ua_batch_eml() -> bytes:
    html = """
    <html><body>
      <a href="https://robota.ua/company1006322/vacancy11412291?utm_source=jobalert">
        Junior AI Developer
      </a>
      <a href="https://robota.ua/company1006322/vacancy11412291?utm_source=jobalert"></a>
      <a href="https://robota.ua/company1006322/vacancy11412291?utm_source=jobalert">
        Київ &nbsp;&nbsp; Farmak
      </a>
      <a href="https://robota.ua/company13611309/vacancy11383538?utm_source=jobalert">
        Software Engineer (Python)
      </a>
      <a href="https://robota.ua/company13611309/vacancy11383538?utm_source=jobalert">
        75 000 грн Київ &nbsp;&nbsp; TechLab
      </a>
      <a href="https://robota.ua/company13611309/vacancy11383538/apply?utm_source=jobalert">
        Відгукнутись на вакансію
      </a>
    </body></html>
    """
    return build_eml("robota.ua <alerts@mailing.rabota.ua>", html)


def robota_ua_solo_eml() -> bytes:
    html = """
    <html><body>
      <p>Віддалена робота</p>
      <a href="https://robota.ua/company5264041/vacancy11393199?utm_source=jobinstant">
        AI Engineer
      </a>
      <p>NovaPay</p>
      <p>Київ</p>
      <p>Develop Python LLM agents and backend APIs. Salary $2000.</p>
      <p>Відгукнутись на вакансію</p>
    </body></html>
    """
    return build_eml("robota.ua <alerts@mailing.rabota.ua>", html)
