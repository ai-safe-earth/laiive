import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

type Mode = "signin" | "signup";

export default function Auth() {
  const navigate = useNavigate();
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);

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

        {/* Google OAuth (D8) is wired on the Supabase side but the provider is
            not enabled yet — the button appears once it is. */}

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
