import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import AuthCard from "../components/AuthCard";
import Field from "../components/Field";
import { useAuth } from "../auth";
import { useFormValidation } from "../useFormValidation";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const v = useFormValidation("login");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(form.email, form.password);
      navigate("/");
    } catch (err) {
      if (!v.fromError(err)) setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Welcome back" subtitle="Log in to your Campus Customs account.">
      <form className="auth-form" onSubmit={submit} noValidate>
        <Field
          label="Email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@yale.edu"
          value={form.email}
          error={v.errors.email}
          onChange={(e) => {
            const next = { ...form, email: e.target.value };
            setForm(next);
            v.change("email", next);
          }}
          onBlur={() => v.blur("email", form)}
        />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="current-password"
          placeholder="••••••••"
          value={form.password}
          error={v.errors.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
        <button className="btn btn-primary full" type="submit" disabled={busy}>
          {busy ? "Logging in…" : "Log In"}
        </button>
        {error && <div className="form-notice error">{error}</div>}
      </form>
      <p className="auth-switch">
        New to Campus Customs? <Link to="/create-account">Create an account</Link>
      </p>
    </AuthCard>
  );
}
