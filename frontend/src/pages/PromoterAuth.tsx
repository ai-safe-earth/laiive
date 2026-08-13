import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { useTranslation } from '@/hooks/useTranslation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ArrowLeft, Loader2, Plus, Building2, Music, Tent, X } from 'lucide-react';
import { toast } from 'sonner';
import { supabase } from '@/integrations/supabase/client';
import { EntityFormDialog, EntityType, EntityFormVariant } from '@/components/entities/EntityFormDialog';

type AuthMode = 'login' | 'signup' | 'upgrade';

interface PendingEntity {
  type: EntityType;
  data: any;
}

const industryRoles = [
  { value: 'promoter', label: 'Event Promoter' },
  { value: 'venue_manager', label: 'Venue Manager' },
  { value: 'artist_manager', label: 'Artist Manager' },
  { value: 'booking_agent', label: 'Booking Agent' },
  { value: 'musician', label: 'Musician / Band Member' },
  { value: 'other', label: 'Other' },
];

const typeConfig = {
  venue: { icon: Building2, label: "Venue", color: "text-cyan-400 bg-cyan-500/20 border-cyan-500/30" },
  band: { icon: Music, label: "Band", color: "text-fuchsia-400 bg-fuchsia-500/20 border-fuchsia-500/30" },
  festival: { icon: Tent, label: "Festival", color: "text-yellow-400 bg-yellow-500/20 border-yellow-500/30" },
};

export default function PromoterAuth() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { user, isLoading: authLoading, isPromoter, signInWithEmail } = useAuth();

  const [mode, setMode] = useState<AuthMode>('login');
  const [isLoading, setIsLoading] = useState(false);

  // Login fields
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // Professional info fields (for signup and upgrade)
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [city, setCity] = useState('');
  const [country, setCountry] = useState('');
  const [industryRole, setIndustryRole] = useState('');

  // Entity management
  const [pendingEntities, setPendingEntities] = useState<PendingEntity[]>([]);
  const [entityDialogOpen, setEntityDialogOpen] = useState(false);
  const [entityDialogType, setEntityDialogType] = useState<EntityType>('venue');
  const [addMenuOpen, setAddMenuOpen] = useState(false);

  // Determine mode based on auth state
  useEffect(() => {
    if (!authLoading) {
      if (user && isPromoter) {
        // Already a promoter, redirect to create page
        navigate('/promoters/create');
      } else if (user && !isPromoter) {
        // Logged in but not a promoter, show upgrade form
        setMode('upgrade');
      }
    }
  }, [user, isPromoter, authLoading, navigate]);

  const handleAddEntity = (type: EntityType) => {
    setEntityDialogType(type);
    setEntityDialogOpen(true);
    setAddMenuOpen(false);
  };

  const handleSaveEntity = async (data: any) => {
    setPendingEntities(prev => [...prev, { type: entityDialogType, data }]);
    setEntityDialogOpen(false);
  };

  const handleRemoveEntity = (index: number) => {
    setPendingEntities(prev => prev.filter((_, i) => i !== index));
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const { error } = await signInWithEmail(email, password);
      if (error) {
        toast.error(error.message);
      }
      // Auth state change will handle redirect
    } catch (err) {
      toast.error('Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!firstName || !lastName || !city || !country || !industryRole) {
      toast.error('Please fill in all professional information');
      return;
    }

    setIsLoading(true);

    try {
      const { data, error } = await supabase.functions.invoke('promoter-signup', {
        body: {
          email,
          password,
          firstName,
          lastName,
          city,
          country,
          industryRole,
          entities: pendingEntities.length > 0 ? pendingEntities : undefined,
        },
      });

      if (error) throw error;
      if (data?.error) throw new Error(data.error);

      toast.success('Account created! Please check your email to confirm.');
      setMode('login');
    } catch (err: any) {
      toast.error(err.message || 'Signup failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpgrade = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!firstName || !lastName || !city || !country || !industryRole) {
      toast.error('Please fill in all professional information');
      return;
    }

    setIsLoading(true);

    try {
      const { data, error } = await supabase.functions.invoke('promoter-signup', {
        body: {
          upgrade: true,
          firstName,
          lastName,
          city,
          country,
          industryRole,
          entities: pendingEntities.length > 0 ? pendingEntities : undefined,
        },
      });

      if (error) throw error;
      if (data?.error) throw new Error(data.error);

      toast.success('Welcome to laiive Pro!');
      // Refresh the page to update auth state
      window.location.href = '/promoters/create';
    } catch (err: any) {
      toast.error(err.message || 'Upgrade failed');
    } finally {
      setIsLoading(false);
    }
  };

  const entitySection = (
    <div className="space-y-3">
      <div className="border-t border-cyan-500/20 pt-4 mt-2" />
      <div className="flex items-center justify-between">
        <Label>Managed Entities</Label>
        <DropdownMenu open={addMenuOpen} onOpenChange={setAddMenuOpen}>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="outline" className="gap-1 border-cyan-500/30 hover:border-cyan-500 h-7 px-2">
              <Plus className="w-3 h-3" />
              Add
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="bg-card border-border">
            <DropdownMenuItem onClick={() => handleAddEntity("venue")} className="gap-2">
              <Building2 className="w-4 h-4 text-cyan-400" />
              Venue
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleAddEntity("band")} className="gap-2">
              <Music className="w-4 h-4 text-fuchsia-400" />
              Band
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => handleAddEntity("festival")} className="gap-2">
              <Tent className="w-4 h-4 text-yellow-400" />
              Festival
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <p className="text-xs text-muted-foreground">
        You can always add or edit this later in Account Settings
      </p>

      {pendingEntities.length > 0 && (
        <div className="space-y-2">
          {pendingEntities.map((entity, index) => {
            const config = typeConfig[entity.type];
            const Icon = config.icon;
            return (
              <div
                key={index}
                className="flex items-center justify-between p-2 rounded-lg bg-muted/50 border border-border/50"
              >
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${config.color} flex items-center gap-1`}>
                    <Icon className="w-3 h-3" />
                    {config.label}
                  </span>
                  <span className="text-sm font-medium">{entity.data.name}</span>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                  onClick={() => handleRemoveEntity(index)}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  const professionalInfoFields = (
    <>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="firstName">First Name</Label>
          <Input
            id="firstName"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            placeholder="John"
            required
            className="bg-background/50 border-cyan-500/30 focus:border-cyan-500 focus-visible:ring-cyan-500/30"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="lastName">Last Name</Label>
          <Input
            id="lastName"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            placeholder="Doe"
            required
            className="bg-background/50 border-cyan-500/30 focus:border-cyan-500 focus-visible:ring-cyan-500/30"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="city">City</Label>
          <Input
            id="city"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="Barcelona"
            required
            className="bg-background/50 border-cyan-500/30 focus:border-cyan-500 focus-visible:ring-cyan-500/30"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="country">Country</Label>
          <Input
            id="country"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            placeholder="Spain"
            required
            className="bg-background/50 border-cyan-500/30 focus:border-cyan-500 focus-visible:ring-cyan-500/30"
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="industryRole">Your Role in the Industry</Label>
        <Select value={industryRole} onValueChange={setIndustryRole}>
          <SelectTrigger className="bg-background/50 border-cyan-500/30 focus:border-cyan-500 focus-visible:ring-cyan-500/30">
            <SelectValue placeholder="Select your role" />
          </SelectTrigger>
          <SelectContent>
            {industryRoles.map((role) => (
              <SelectItem key={role.value} value={role.value}>
                {role.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {entitySection}
    </>
  );

  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#1a1a1a] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-cyan-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#1a1a1a] flex flex-col">
      {/* Header */}
      <header className="p-4 flex items-center justify-between border-b border-cyan-500/20">
        <button
          onClick={() => navigate('/promoters')}
          className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
          <span>Back</span>
        </button>
        <div className="flex items-center gap-2">
          <span className="text-xl font-bold text-foreground">laiive</span>
          <span className="text-xs px-2 py-0.5 bg-accent/20 text-accent rounded-full border border-accent/30">
            PRO
          </span>
        </div>
        <button
          onClick={() => navigate("/")}
          className="font-ibm-plex text-[10px] text-muted-foreground hover:text-primary transition-colors flex items-center gap-0.5"
        >
          <span className="text-[10px]">🫦</span>
          <span>laiive</span>
        </button>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-background/50 border-accent/30">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">
              {mode === 'login' && 'Promoter Login'}
              {mode === 'signup' && 'Become a Promoter'}
              {mode === 'upgrade' && 'Upgrade to Pro'}
            </CardTitle>
            <CardDescription>
              {mode === 'login' && 'Sign in to your promoter account'}
              {mode === 'signup' && 'Create your promoter account with professional info'}
              {mode === 'upgrade' && 'Complete your profile to start publishing events'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {mode === 'login' && (
              <form onSubmit={handleLogin} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    required
                    className="bg-background/50 border-cyan-500/30 focus:border-cyan-500 focus-visible:ring-cyan-500/30"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="bg-background/50 border-accent/30 focus:border-accent focus-visible:ring-accent/30"
                  />
                </div>
                <Button
                  type="submit"
                  className="w-full bg-accent hover:bg-cyan-600 text-accent-foreground font-semibold"
                  disabled={isLoading}
                >
                  {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Sign In'}
                </Button>
                <p className="text-center text-sm text-muted-foreground">
                  Don't have an account?{' '}
                  <button
                    type="button"
                    onClick={() => setMode('signup')}
                    className="text-cyan-400 hover:underline"
                  >
                    Sign up as a promoter
                  </button>
                </p>
              </form>
            )}

            {mode === 'signup' && (
              <form onSubmit={handleSignup} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    required
                    className="bg-background/50 border-cyan-500/30 focus:border-cyan-500 focus-visible:ring-cyan-500/30"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    minLength={6}
                    className="bg-background/50 border-cyan-500/30 focus:border-cyan-500 focus-visible:ring-cyan-500/30"
                  />
                </div>

                <div className="border-t border-cyan-500/20 pt-4 mt-4">
                  <p className="text-sm text-muted-foreground mb-4">Professional Information</p>
                  <div className="space-y-4">
                    {professionalInfoFields}
                  </div>
                </div>

                <Button
                  type="submit"
                  className="w-full bg-accent hover:bg-cyan-600 text-accent-foreground font-semibold"
                  disabled={isLoading}
                >
                  {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create Promoter Account'}
                </Button>
                <p className="text-center text-sm text-muted-foreground">
                  Already have an account?{' '}
                  <button
                    type="button"
                    onClick={() => setMode('login')}
                    className="text-cyan-400 hover:underline"
                  >
                    Sign in
                  </button>
                </p>
              </form>
            )}

            {mode === 'upgrade' && (
              <form onSubmit={handleUpgrade} className="space-y-4">
                <div className="bg-cyan-500/10 border border-cyan-500/30 rounded-lg p-3 mb-4">
                  <p className="text-sm text-cyan-400">
                    You're signed in as <strong>{user?.email}</strong>. Complete your profile below to become a promoter.
                  </p>
                </div>

                {professionalInfoFields}

                <Button
                  type="submit"
                  className="w-full bg-accent hover:bg-cyan-600 text-accent-foreground font-semibold"
                  disabled={isLoading}
                >
                  {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Upgrade to Pro'}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </main>

      {/* Entity Form Dialog */}
      <EntityFormDialog
        open={entityDialogOpen}
        onOpenChange={setEntityDialogOpen}
        entityType={entityDialogType}
        onSave={handleSaveEntity}
        variant="pro"
      />
    </div>
  );
}
