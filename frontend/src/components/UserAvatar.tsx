import { User, LogOut, Settings } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useNavigate } from "react-router-dom";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface UserAvatarProps {
  className?: string;
  variant?: "default" | "pro";
}

export const UserAvatar = ({ className, variant = "default" }: UserAvatarProps) => {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const isPro = variant === "pro";

  // Get initials from email
  const getInitials = (email: string) => {
    return email.charAt(0).toUpperCase();
  };

  if (!user) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={() => navigate(isPro ? '/promoters/auth' : '/auth')}
              className={cn(
                "w-10 h-10 rounded-lg flex items-center justify-center transition-colors",
                isPro
                  ? "bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 border border-cyan-500/30"
                  : "bg-muted text-muted-foreground hover:text-foreground hover:bg-muted/80",
                className
              )}
            >
              <User className="w-5 h-5" />
            </button>
          </TooltipTrigger>
          <TooltipContent>
            <p className="text-xs">Sign in</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className={cn(
            "w-10 h-10 rounded-lg flex items-center justify-center font-bold text-lg transition-colors",
            isPro
              ? "bg-cyan-500 text-white hover:bg-cyan-400 border border-cyan-400/50"
              : "bg-primary text-primary-foreground hover:bg-primary/90",
            className
          )}
        >
          {getInitials(user.email || 'U')}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48 bg-card border-border">
        <DropdownMenuItem className="text-xs text-muted-foreground cursor-default">
          {user.email}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => navigate('/account/settings')}>
          <Settings className="w-4 h-4 mr-2" />
          Account settings
        </DropdownMenuItem>
        <DropdownMenuItem onClick={signOut} className="text-destructive focus:text-destructive">
          <LogOut className="w-4 h-4 mr-2" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
