import { FormEvent, useState } from 'react';

interface ChatWidgetProps {
  className?: string;
}

interface WidgetFormState {
  email: string;
  subject: string;
  message: string;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
}

const initialFormState: WidgetFormState = {
  email: '',
  subject: '',
  message: '',
  priority: 'MEDIUM',
};

export function ChatWidget({ className = '' }: ChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [formState, setFormState] = useState<WidgetFormState>(initialFormState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setFeedback('Submitting your request and kicking off AI triage…');

    try {
      const createResponse = await fetch('http://localhost:8000/api/v1/tickets/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: formState.subject,
          description: formState.message,
          customer_email: formState.email,
          priority: formState.priority,
        }),
      });

      if (!createResponse.ok) {
        const detail = await createResponse.text();
        throw new Error(detail || 'Ticket submission failed.');
      }

      const createdTicket = (await createResponse.json()) as { id?: number };
      const triageResponse = await fetch(`http://localhost:8000/api/v1/tickets/${createdTicket.id}/triage`, {
        method: 'POST',
      });

      if (!triageResponse.ok) {
        const detail = await triageResponse.text();
        throw new Error(detail || 'AI triage could not be completed.');
      }

      const triageData = (await triageResponse.json()) as {
        message?: string;
        decision?: { suggested_response?: string; execution_track?: string; confidence_score?: number };
      };

      setFeedback(
        triageData.message ?? 'Your request was accepted and routed through AI triage.'
      );
      setFormState(initialFormState);
      setTimeout(() => setFeedback(null), 5000);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unknown error.');
      setFeedback(null);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className={`fixed bottom-4 right-4 z-50 ${className}`}>
      {!isOpen ? (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="flex items-center gap-3 rounded-full border border-cyan-400/40 bg-slate-900 px-4 py-3 shadow-2xl shadow-cyan-500/10 transition hover:-translate-y-0.5"
        >
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-cyan-500/20 text-xl">💬</span>
          <span className="text-sm font-semibold text-slate-100">Customer chat widget</span>
        </button>
      ) : (
        <div className="w-[min(92vw,420px)] rounded-3xl border border-slate-700 bg-slate-900/95 p-4 shadow-2xl shadow-slate-950/60 backdrop-blur">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.3em] text-cyan-400">SupportFlow</p>
              <h3 className="text-lg font-semibold text-slate-100">Customer chat</h3>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="rounded-full border border-slate-700 px-3 py-1 text-sm text-slate-300"
            >
              Close
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="mb-1 block text-sm text-slate-400" htmlFor="customer-email">
                Customer email
              </label>
              <input
                id="customer-email"
                type="email"
                required
                value={formState.email}
                onChange={(event) => setFormState((prev) => ({ ...prev, email: event.target.value }))}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-0"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm text-slate-400" htmlFor="customer-subject">
                Subject
              </label>
              <input
                id="customer-subject"
                type="text"
                required
                value={formState.subject}
                onChange={(event) => setFormState((prev) => ({ ...prev, subject: event.target.value }))}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-0"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm text-slate-400" htmlFor="customer-message">
                Initial message
              </label>
              <textarea
                id="customer-message"
                required
                rows={4}
                value={formState.message}
                onChange={(event) => setFormState((prev) => ({ ...prev, message: event.target.value }))}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-0"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm text-slate-400" htmlFor="customer-priority">
                Priority
              </label>
              <select
                id="customer-priority"
                value={formState.priority}
                onChange={(event) =>
                  setFormState((prev) => ({ ...prev, priority: event.target.value as WidgetFormState['priority'] }))
                }
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-0"
              >
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
                <option value="URGENT">Urgent</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-xl bg-cyan-500 px-3 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isSubmitting ? 'Sending…' : 'Send to SupportFlow'}
            </button>
          </form>

          {feedback ? (
            <div className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-300">
              {feedback}
            </div>
          ) : null}

          {error ? (
            <div className="mt-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300">
              {error}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
