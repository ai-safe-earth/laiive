import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

type Mode = "signin" | "signup";

export default function Auth() {
  const navigate = useNavigate();
  const { signIn, signInWithGoogle, signUp } = useAuth();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);

  const googleSignIn = async () => {
    setBusy(true);
    try {
      await signInWithGoogle(); // navigates away; busy stays on until the redirect
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Google sign-in failed");
      setBusy(false);
    }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      if (mode === "signin") {
        await signIn(email, password);
        navigate("/");
      } else {
        await signUp(email, password, displayName || undefined);
        toast.success("Check your inbox to confirm the address, then sign in.");
        setMode("signin");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center bg-background p-6">
      <Link to="/" className="mb-8 flex items-end gap-1">
        <span className="pb-0.5 text-2xl">🫦</span>
        <span className="font-montserrat text-xl font-bold text-primary">laiive</span>
      </Link>

      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-4 rounded-lg border border-border bg-card p-6"
      >
        <h1 className="font-montserrat text-lg font-bold text-foreground">
          {mode === "signin" ? "sign in" : "create an account"}
        </h1>

        {mode === "signup" && (
          <Input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="display name (optional)"
            autoComplete="nickname"
          />
        )}

        <Input
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="email"
          autoComplete="email"
        />
        <Input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="password"
          autoComplete={mode === "signin" ? "current-password" : "new-password"}
        />

        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? "…" : mode === "signin" ? "sign in" : "sign up"}
        </Button>

        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="h-px flex-1 bg-border" />
          or
          <span className="h-px flex-1 bg-border" />
        </div>

        <Button
          type="button"
          variant="outline"
          className="w-full"
          disabled={busy}
          onClick={googleSignIn}
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
            <path
              fill="#4285F4"
              d="M23.5 12.27c0-.85-.08-1.66-.22-2.45H12v4.64h6.45a5.52 5.52 0 0 1-2.39 3.62v3h3.87c2.26-2.09 3.57-5.17 3.57-8.81Z"
            />
            <path
              fill="#34A853"
              d="M12 24c3.24 0 5.96-1.07 7.93-2.91l-3.87-3.01c-1.07.72-2.45 1.15-4.06 1.15-3.12 0-5.77-2.11-6.71-4.95H1.29v3.1A11.99 11.99 0 0 0 12 24Z"
            />
            <path
              fill="#FBBC05"
              d="M5.29 14.28A7.21 7.21 0 0 1 4.91 12c0-.79.14-1.56.38-2.28v-3.1H1.29a12 12 0 0 0 0 10.76l4-3.1Z"
            />
            <path
              fill="#EA4335"
              d="M12 4.77c1.76 0 3.34.61 4.58 1.8l3.44-3.44C17.95 1.19 15.24 0 12 0A11.99 11.99 0 0 0 1.29 6.62l4 3.1C6.23 6.88 8.88 4.77 12 4.77Z"
            />
          </svg>
          continue with google
        </Button>

        <button
          type="button"
          onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
          className="w-full text-center text-xs text-muted-foreground hover:text-primary"
        >
          {mode === "signin" ? "no account? sign up" : "already have an account? sign in"}
        </button>
      </form>

      <Link to="/" className="mt-6 text-xs text-muted-foreground hover:text-primary">
        continue without an account →
      </Link>
    </div>
  );
}
