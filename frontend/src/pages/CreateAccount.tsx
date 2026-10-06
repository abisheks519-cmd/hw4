import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import AuthCard from "../components/AuthCard";
import Field from "../components/Field";
import { useAuth } from "../auth";
import { useFormValidation } from "../useFormValidation";

type Form = { first_name: string; last_name: string; email: string; password: string; confirm_password: string };

export default function CreateAccount() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState<Form>({ first_name: "", last_name: "", email: "", password: "", confirm_password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const v = useFormValidation("signup");

  const field = (key: keyof Form, also: string[] = []) => ({
    name: key,
    value: form[key],
    error: v.errors[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
      const next = { ...form, [key]: e.target.value };
      setForm(next);
      v.change(key, next, also);
    },
    onBlur: () => v.blur(key, form),
  });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signup(form);
      navigate("/");
    } catch (err) {
      if (!v.fromError(err)) setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Create your account" subtitle="Join Campus Customs to save your cart and your chats with our assistant.">
      <form className="auth-form" onSubmit={submit} noValidate>
        <div className="form-row">
          <Field label="First name" autoComplete="given-name" {...field("first_name")} />
          <Field label="Last name" autoComplete="family-name" {...field("last_name")} />
        </div>
        <Field label="Email" type="email" autoComplete="email" placeholder="you@yale.edu" {...field("email")} />
        <Field label="Password" type="password" autoComplete="new-password" placeholder="At least 8 characters" hint="8+ characters with at least one letter and one number" {...field("password", ["confirm_password"])} />
        <Field label="Confirm password" type="password" autoComplete="new-password" {...field("confirm_password")} />
        <button className="btn btn-primary full" type="submit" disabled={busy}>
          {busy ? "Creating account…" : "Create Account"}
        </button>
        {error && <div className="form-notice error">{error}</div>}
      </form>
      <p className="auth-switch">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </AuthCard>
  );
}
