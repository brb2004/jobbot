const SECTIONS: [string, string[]][] = [
  ['What we store', [
    'Your email address and a one-way hash of your password. The password itself is never stored.',
    'The text of the resume you upload and the skills found in it.',
    'Your preferences (titles, locations, years of experience) and your match results.',
  ]],
  ['What we use it for', [
    'Matching you to job postings and emailing you your top matches each week. Nothing else.',
    'Matching runs entirely on our server. Your resume is never sent to an AI service or any other third party.',
    'We never sell or share your data, and there are no ads.',
  ]],
  ['Who else touches it', [
    'Cloudflare carries traffic to the site and handles the secure (HTTPS) connection.',
    'Google (Gmail) delivers our emails, so it sees your address and the email content.',
    'The server is in Texas. Its logs include IP addresses, used only to block abuse such as password guessing.',
  ]],
  ['Cookies', [
    'One cookie keeps you logged in. No tracking or analytics cookies.',
  ]],
  ['Deleting your data', [
    'Preferences → Delete account removes your account, resume and matches right away.',
    'Nightly backups are kept for 7 days, so a deleted account is fully gone within a week.',
    'Questions: reply to any JobMatch email.',
  ]],
]

export function Privacy() {
  return (
    <main className="min-h-screen bg-slate-50 px-4 py-10">
      <article className="mx-auto max-w-2xl space-y-6 rounded-xl bg-white p-6 shadow">
        <header>
          <h1 className="text-2xl font-semibold">Privacy</h1>
          <p className="text-sm text-slate-500">Last updated November 10, 2026</p>
        </header>
        {SECTIONS.map(([title, lines]) => (
          <section key={title}>
            <h2 className="font-medium">{title}</h2>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
              {lines.map((l) => <li key={l}>{l}</li>)}
            </ul>
          </section>
        ))}
        <a href="/" className="inline-block text-sm text-slate-600 underline">Back to JobMatch</a>
      </article>
    </main>
  )
}
