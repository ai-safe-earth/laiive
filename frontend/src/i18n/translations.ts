export type Language = 'en' | 'es' | 'it' | 'ca';

/** Every field of an EventDraft the form renders, in form order. */
export type DraftFieldKey =
  | 'name'
  | 'artists'
  | 'start_at'
  | 'venue'
  | 'address'
  | 'city'
  | 'price_min'
  | 'price_max'
  | 'price_currency'
  | 'genre'
  | 'ticket_url'
  | 'description';

export interface Translations {
  chat: {
    placeholder: string;
    statusReading: string;
    statusSearching: string;
    /** Sent verbatim, so these are queries in the reader's language, not labels. */
    examples: string[];
    statusWriting: string;
    rateLimited: string;
    rateLimitedAnon: string; // markdown, links to /auth
    sessionExpired: string; // markdown, links to /auth
    genericError: string;
    stop: string;
    send: string;
    feedbackDown: string;
    feedbackReasonPlaceholder: string;
    feedbackThanks: string;
  };
  auth: {
    signInTitle: string;
    signUpTitle: string;
    displayNamePlaceholder: string;
    emailPlaceholder: string;
    passwordPlaceholder: string;
    signIn: string;
    signUp: string;
    or: string;
    google: string;
    toSignUp: string;
    toSignIn: string;
    withoutAccount: string;
    checkInbox: string;
    /** The OAuth waiting room. */
    finishing: string;
    /** The promoter door only. */
    orgPlaceholder: string;
    orgRequired: string;
    promoterSetupFailed: string;
    /** The row landed, the token did not — see becomePromoter. */
    promoterSessionStale: string;
    failed: string;
    googleFailed: string;
    proInvite: string;
    proCta: string;
  };
  account: {
    back: string;
    title: string;
    you: string;
    displayName: string;
    displayNamePlaceholder: string;
    language: string;
    languageNote: string;
    save: string;
    promoter: string;
    promoterNote: string;
    /** Same section, shown to an account that is not a promoter yet. */
    becomePromoter: string;
    becomePromoterNote: string;
    becomePromoterCta: string;
    becamePromoter: string;
    organisation: string;
    organisationPlaceholder: string;
    website: string;
    phone: string;
    venues: string;
    artists: string;
    add: string;
    remove: (item: string) => string;
    profileSaved: string;
    promoterSaved: string;
    saveFailed: string;
    orgRequired: string;
  };
  pro: {
    needsPro: string;
    becomeProLink: string;
    signInLink: string;
    onboardingSteps: string[];
    onboardingDismiss: string;
    statusExtracting: string;
    readingFile: (name: string) => string;
    notPromoter: string;
    genericError: string;
    couldNotRead: string;
    published: (name: string) => string;
    publishedMarker: (name: string, k: number, n: number) => string;
    walkComplete: (n: number) => string;
    alreadyExists: string;
    publishFailed: string;
    eventOf: (k: number, n: number) => string;
    attach: string;
    send: string;
    placeholder: string;
  };
  form: {
    title: string;
    stillNeeded: (n: number) => string;
    labels: Record<DraftFieldKey, string>;
    missingPlaceholder: string;
    ticketNoteAria: string;
    ticketNote: string;
    ticketInvalid: string;
    publish: string;
    publishing: string;
    fillHint: (fields: string) => string;
    addArtist: string;
    removeArtist: string;
    artistPlaceholder: string;
    addressOnFile: string;
    venueSuggestionsAria: string;
  };
  cards: {
    free: string;
    readMore: string;
    less: string;
    map: string;
    hideMap: string;
    openMaps: string;
    approximate: string;
    tickets: string;
    save: string;
    saved: string;
    webTitle: string;
    webAria: string;
    webMissing: string;
    webSourceFallback: string;
    webClaim: string;
    verifiedAria: string;
    verifiedTitle: string;
    fieldTime: string;
    fieldPrice: string;
    fieldLocation: string;
  };
  /** The saved list. Named apart from menu.saved, which is the way in. */
  savedPage: {
    title: string;
    empty: string;
    emptyHint: string;
    upcoming: string;
    past: string;
    failed: string;
    retry: string;
    back: string;
  };
  menu: {
    saved: string;
    account: string;
    settings: string;
    pro: string;
    toLaiive: string;
    signOut: string;
    signIn: string;
    aria: string;
  };
  voice: {
    speak: string;
    stop: string;
    denied: string;
    nothing: string;
    failed: string;
  };
  notFound: {
    back: string;
  };
}

export const translations: Record<Language, Translations> = {
  en: {
    chat: {
      placeholder: "search your event here…",
      statusReading: "reading your question…",
      statusSearching: "searching for events…",
      examples: [
        "rock concerts this weekend near me",
        "concerts today near me",
        "rock concerts this week in Torino",
      ],
      statusWriting: "writing…",
      rateLimited: "You are sending requests a little fast — give it a minute.",
      rateLimitedAnon: "That's the free quota for now. [Sign in →](/auth) for a higher limit.",
      sessionExpired: "Your session expired. [Sign in again →](/auth)",
      genericError: "Something went wrong.",
      stop: "Stop",
      send: "Send",
      feedbackDown: "Not helpful",
      feedbackReasonPlaceholder: "What went wrong? (optional)",
      feedbackThanks: "Thanks for the feedback",
    },
    auth: {
      signInTitle: "sign in",
      signUpTitle: "create an account",
      displayNamePlaceholder: "display name (optional)",
      emailPlaceholder: "email",
      passwordPlaceholder: "password", // pragma: allowlist secret
      signIn: "sign in",
      signUp: "sign up",
      or: "or",
      google: "continue with google",
      toSignUp: "no account? sign up",
      toSignIn: "already have an account? sign in",
      withoutAccount: "continue without an account →",
      checkInbox: "Check your inbox to confirm the address, then sign in.",
      finishing: "finishing sign-in…",
      orgPlaceholder: "organisation — venue, label, collective…",
      orgRequired: "the organisation name is required",
      promoterSetupFailed: "Account created, but promoter setup did not finish — add it in your account.",
      promoterSessionStale: "You're a promoter now, but this session is still the old one — sign in again to open pro.",
      failed: "Authentication failed",
      googleFailed: "Google sign-in failed",
      proInvite: "promoter, musician, venue owner?",
      proCta: "sign up as a pro — free, and your nights go straight on laiive →",
    },
    account: {
      back: "back",
      title: "account",
      you: "you",
      displayName: "display name",
      displayNamePlaceholder: "how we greet you",
      language: "language",
      languageNote: "Saved to your account — the assistant still answers in whatever language you write in.",
      save: "save",
      promoter: "promoter",
      promoterNote: "What you run. Submitted events are linked to you regardless.",
      becomePromoter: "publish your own nights",
      becomePromoterNote: "Tell us what you run and this becomes a promoter account — publishing opens straight away.",
      becomePromoterCta: "become a promoter",
      becamePromoter: "you're a promoter now — publishing is open",
      organisation: "organisation",
      organisationPlaceholder: "venue, label, collective…",
      website: "website",
      phone: "phone",
      venues: "venues you manage",
      artists: "artists you manage",
      add: "add",
      remove: (item) => `remove ${item}`,
      profileSaved: "profile saved",
      promoterSaved: "promoter details saved",
      saveFailed: "could not save",
      orgRequired: "the organisation name is required",
    },
    pro: {
      needsPro: "Publishing events needs a promoter account.",
      becomeProLink: "set up your promoter details and publish →",
      signInLink: "sign in →",
      onboardingSteps: [
        "Drop a flyer, a PDF or a photo — or just type it, or say it out loud.",
        "laiive reads it and fills the form. Every field is yours to correct.",
        "Confirm, and the event is live.",
        "Somebody searching laiive for a night like yours finds it.",
      ],
      onboardingDismiss: "don't show this again",
      statusExtracting: "reading what you sent…",
      readingFile: (name) => `reading ${name}…`,
      notPromoter: "Your account is not a promoter account yet.",
      genericError: "Something went wrong",
      couldNotRead: "Could not read that file",
      published: (name) => `Published — ${name} is live`,
      publishedMarker: (name, k, n) => `Published "${name}" (event ${k} of ${n}).`,
      walkComplete: (n) =>
        n > 1
          ? `All ${n} events are live on laiive. Send another listing whenever you're ready.`
          : `Your event is live on laiive. Send another listing whenever you're ready.`,
      alreadyExists: "That event is already on laiive.",
      publishFailed: "Could not publish",
      eventOf: (k, n) => `event ${k} of ${n}`,
      attach: "Attach a flyer, document or recording",
      send: "Send",
      placeholder: "artist, venue, date, price…",
    },
    form: {
      title: "event details",
      stillNeeded: (n) => `${n} still needed`,
      labels: {
        name: "event name",
        artists: "artists",
        start_at: "starts at",
        venue: "venue",
        address: "address",
        city: "city",
        price_min: "price from",
        price_max: "price to",
        price_currency: "currency",
        genre: "genre",
        ticket_url: "ticket link",
        description: "description",
      },
      missingPlaceholder: "the assistant could not find this",
      ticketNoteAria: "about the ticket link",
      ticketNote:
        "laiive does not sell tickets yet — this link sends people straight to wherever you already sell them. Ticketing here is on its way.",
      ticketInvalid: "that does not look like a web address",
      publish: "publish to laiive",
      publishing: "publishing…",
      fillHint: (fields) => `fill ${fields} — by typing here or just telling the assistant`,
      addArtist: "+ add artist",
      removeArtist: "remove artist",
      artistPlaceholder: "artist or band name",
      addressOnFile: "on file at laiive",
      venueSuggestionsAria: "venues laiive already knows",
    },
    cards: {
      free: "free",
      readMore: "+ read more",
      less: "− less",
      map: "map",
      hideMap: "hide map",
      openMaps: "open in Google Maps",
      approximate: "Approximate — the exact address of this venue is not known yet.",
      tickets: "tickets",
      save: "save",
      saved: "saved",
      webAria: "Where did this come from?",
      webSourceFallback: "see the original listing",
      webClaim:
        "Putting this night on? Add it from a promoter account and it becomes yours to correct.",
      verifiedAria: "Who confirmed this?",
      verifiedTitle:
        "Confirmed by a promoter of this event, from their own account — the times, the price and the door are as they entered them.",
      webTitle:
        "We found this listing with our own web search. The promoter has not confirmed it, so anything the page did not state is left blank rather than guessed.",
      webMissing: "Not stated on the page",
      fieldTime: "start time",
      fieldPrice: "price",
      fieldLocation: "exact address",
    },
    savedPage: {
      title: "saved",
      empty: "Nothing saved yet.",
      emptyHint: "Save a card and it waits for you here.",
      upcoming: "coming up",
      past: "already happened",
      failed: "could not load your saved events",
      retry: "try again",
      back: "back",
    },
    menu: {
      account: "account",
      signOut: "sign out",
      signIn: "sign in",
      settings: "settings",
      pro: "laiive pro",
      toLaiive: "back to laiive",
      saved: "saved",
      aria: "Account menu",
    },
    voice: {
      speak: "Speak instead of typing",
      stop: "Stop and transcribe",
      denied: "Microphone permission denied",
      nothing: "Nothing came through — say it again",
      failed: "Transcription failed",
    },
    notFound: {
      back: "back to the chat →",
    },
  },
  es: {
    chat: {
      placeholder: "busca tu evento aquí…",
      statusReading: "leyendo tu pregunta…",
      statusSearching: "buscando eventos…",
      examples: [
        "conciertos de rock este fin de semana cerca de mí",
        "conciertos hoy cerca de mí",
        "conciertos de rock esta semana en Turín",
      ],
      statusWriting: "escribiendo…",
      rateLimited: "Estás enviando mensajes muy rápido — dale un minuto.",
      rateLimitedAnon: "Ese es el límite gratuito por ahora. [Inicia sesión →](/auth) para un límite mayor.",
      sessionExpired: "Tu sesión ha caducado. [Vuelve a iniciar sesión →](/auth)",
      genericError: "Algo ha ido mal.",
      stop: "Detener",
      send: "Enviar",
      feedbackDown: "No útil",
      feedbackReasonPlaceholder: "¿Qué ha fallado? (opcional)",
      feedbackThanks: "Gracias por tu opinión",
    },
    auth: {
      signInTitle: "inicia sesión",
      signUpTitle: "crea una cuenta",
      displayNamePlaceholder: "nombre visible (opcional)",
      emailPlaceholder: "email",
      passwordPlaceholder: "contraseña", // pragma: allowlist secret
      signIn: "inicia sesión",
      signUp: "regístrate",
      or: "o",
      google: "continúa con google",
      toSignUp: "¿sin cuenta? regístrate",
      toSignIn: "¿ya tienes cuenta? inicia sesión",
      withoutAccount: "continúa sin cuenta →",
      checkInbox: "Revisa tu correo para confirmar la dirección y luego inicia sesión.",
      finishing: "completando el inicio de sesión…",
      orgPlaceholder: "organización — sala, sello, colectivo…",
      orgRequired: "el nombre de la organización es obligatorio",
      promoterSetupFailed: "Cuenta creada, pero no se completó el alta de promotor — añádelo en tu cuenta.",
      promoterSessionStale: "Ya eres promotor, pero esta sesión sigue siendo la anterior — vuelve a iniciar sesión para abrir pro.",
      failed: "No se pudo iniciar sesión",
      googleFailed: "No se pudo iniciar sesión con Google",
      proInvite: "¿promotor, músico, dueño de una sala?",
      proCta: "regístrate como pro — gratis, y tus noches entran directas en laiive →",
    },
    account: {
      back: "atrás",
      title: "cuenta",
      you: "tú",
      displayName: "nombre visible",
      displayNamePlaceholder: "cómo te saludamos",
      language: "idioma",
      languageNote: "Se guarda en tu cuenta — el asistente sigue respondiendo en el idioma en que escribas.",
      save: "guardar",
      promoter: "promotor",
      promoterNote: "Lo que gestionas. Los eventos enviados se vinculan a ti igualmente.",
      becomePromoter: "publica tus propias noches",
      becomePromoterNote: "Cuéntanos qué gestionas y esta cuenta pasa a ser de promotor — podrás publicar al momento.",
      becomePromoterCta: "hazte promotor",
      becamePromoter: "ya eres promotor — puedes publicar",
      organisation: "organización",
      organisationPlaceholder: "sala, sello, colectivo…",
      website: "web",
      phone: "teléfono",
      venues: "salas que gestionas",
      artists: "artistas que gestionas",
      add: "añadir",
      remove: (item) => `quitar ${item}`,
      profileSaved: "perfil guardado",
      promoterSaved: "datos de promotor guardados",
      saveFailed: "no se pudo guardar",
      orgRequired: "el nombre de la organización es obligatorio",
    },
    pro: {
      needsPro: "Para publicar eventos necesitas una cuenta de promotor.",
      becomeProLink: "configura tus datos de promotor y publica →",
      signInLink: "inicia sesión →",
      onboardingSteps: [
        "Suelta un cartel, un PDF o una foto — o escríbelo, o dilo en voz alta.",
        "laiive lo lee y rellena el formulario. Todos los campos son tuyos para corregir.",
        "Confirma, y el evento está publicado.",
        "Alguien que busque en laiive una noche como la tuya lo encuentra.",
      ],
      onboardingDismiss: "no volver a mostrar",
      statusExtracting: "leyendo lo que has enviado…",
      readingFile: (name) => `leyendo ${name}…`,
      notPromoter: "Tu cuenta aún no es de promotor.",
      genericError: "Algo ha ido mal",
      couldNotRead: "No se pudo leer ese archivo",
      published: (name) => `Publicado — ${name} ya está en laiive`,
      publishedMarker: (name, k, n) => `He publicado "${name}" (evento ${k} de ${n}).`,
      walkComplete: (n) =>
        n > 1
          ? `Los ${n} eventos ya están en laiive. Envía otro listado cuando quieras.`
          : `Tu evento ya está en laiive. Envía otro listado cuando quieras.`,
      alreadyExists: "Ese evento ya está en laiive.",
      publishFailed: "No se pudo publicar",
      eventOf: (k, n) => `evento ${k} de ${n}`,
      attach: "Adjunta un cartel, documento o grabación",
      send: "Enviar",
      placeholder: "artista, sala, fecha, precio…",
    },
    form: {
      title: "detalles del evento",
      stillNeeded: (n) => (n === 1 ? "falta 1" : `faltan ${n}`),
      labels: {
        name: "nombre del evento",
        artists: "artistas",
        start_at: "empieza",
        venue: "sala",
        address: "dirección",
        city: "ciudad",
        price_min: "precio desde",
        price_max: "precio hasta",
        price_currency: "moneda",
        genre: "género",
        ticket_url: "enlace de entradas",
        description: "descripción",
      },
      missingPlaceholder: "el asistente no pudo encontrarlo",
      ticketNoteAria: "sobre el enlace de entradas",
      ticketNote:
        "laiive todavía no vende entradas — este enlace lleva directamente a donde ya las vendes. La venta aquí llegará.",
      ticketInvalid: "eso no parece una dirección web",
      publish: "publicar en laiive",
      publishing: "publicando…",
      fillHint: (fields) => `rellena ${fields} — escribiendo aquí o diciéndoselo al asistente`,
      addArtist: "+ añadir artista",
      removeArtist: "quitar artista",
      artistPlaceholder: "nombre del artista o grupo",
      addressOnFile: "registrada en laiive",
      venueSuggestionsAria: "salas que laiive ya conoce",
    },
    cards: {
      free: "gratis",
      readMore: "+ leer más",
      less: "− menos",
      map: "mapa",
      hideMap: "ocultar mapa",
      openMaps: "abrir en Google Maps",
      approximate: "Aproximado — todavía no se conoce la dirección exacta de este local.",
      tickets: "entradas",
      save: "guardar",
      saved: "guardado",
      webAria: "¿De dónde sale esto?",
      webSourceFallback: "ver el anuncio original",
      webClaim:
        "¿Organizas esta noche? Añádela desde una cuenta de promotor y podrás corregirla tú.",
      verifiedAria: "¿Quién lo ha confirmado?",
      verifiedTitle:
        "Confirmado por un promotor de este evento, desde su propia cuenta: la hora, el precio y la puerta son los que él indicó.",
      webTitle:
        "Encontramos este anuncio con nuestra propia búsqueda web. El promotor no lo ha confirmado, así que lo que la página no decía se deja en blanco en vez de inventarlo.",
      webMissing: "La página no lo indicaba",
      fieldTime: "hora de inicio",
      fieldPrice: "precio",
      fieldLocation: "dirección exacta",
    },
    savedPage: {
      title: "guardados",
      empty: "Aún no has guardado nada.",
      emptyHint: "Guarda una tarjeta y te espera aquí.",
      upcoming: "próximos",
      past: "ya pasaron",
      failed: "no se pudieron cargar tus guardados",
      retry: "reintentar",
      back: "atrás",
    },
    menu: {
      account: "cuenta",
      signOut: "cerrar sesión",
      signIn: "inicia sesión",
      settings: "ajustes",
      pro: "laiive pro",
      toLaiive: "volver a laiive",
      saved: "guardados",
      aria: "Menú de cuenta",
    },
    voice: {
      speak: "Habla en vez de escribir",
      stop: "Para y transcribe",
      denied: "Sin permiso de micrófono",
      nothing: "No llegó nada — dilo otra vez",
      failed: "No se pudo transcribir",
    },
    notFound: {
      back: "volver al chat →",
    },
  },
  it: {
    chat: {
      placeholder: "cerca il tuo evento qui…",
      statusReading: "leggo la tua domanda…",
      statusSearching: "cerco eventi…",
      examples: [
        "concerti rock questo fine settimana vicino a me",
        "concerti oggi vicino a me",
        "concerti rock questa settimana a Torino",
      ],
      statusWriting: "scrivo…",
      rateLimited: "Stai inviando richieste un po' troppo in fretta — aspetta un minuto.",
      rateLimitedAnon: "Questo è il limite gratuito per ora. [Accedi →](/auth) per un limite più alto.",
      sessionExpired: "La tua sessione è scaduta. [Accedi di nuovo →](/auth)",
      genericError: "Qualcosa è andato storto.",
      stop: "Interrompi",
      send: "Invia",
      feedbackDown: "Non utile",
      feedbackReasonPlaceholder: "Cosa non andava? (facoltativo)",
      feedbackThanks: "Grazie per il feedback",
    },
    auth: {
      signInTitle: "accedi",
      signUpTitle: "crea un account",
      displayNamePlaceholder: "nome visibile (opzionale)",
      emailPlaceholder: "email",
      passwordPlaceholder: "password", // pragma: allowlist secret
      signIn: "accedi",
      signUp: "registrati",
      or: "o",
      google: "continua con google",
      toSignUp: "niente account? registrati",
      toSignIn: "hai già un account? accedi",
      withoutAccount: "continua senza account →",
      checkInbox: "Controlla la tua casella per confermare l'indirizzo, poi accedi.",
      finishing: "completamento dell'accesso…",
      orgPlaceholder: "organizzazione — locale, etichetta, collettivo…",
      orgRequired: "il nome dell'organizzazione è obbligatorio",
      promoterSetupFailed: "Account creato, ma la configurazione da promoter non è andata a buon fine — completala nel tuo account.",
      promoterSessionStale: "Ora sei un promoter, ma questa sessione è ancora quella vecchia — accedi di nuovo per aprire pro.",
      failed: "Autenticazione non riuscita",
      googleFailed: "Accesso con Google non riuscito",
      proInvite: "promoter, musicista, gestore di un locale?",
      proCta: "registrati come pro — gratis, e le tue serate entrano dritte su laiive →",
    },
    account: {
      back: "indietro",
      title: "account",
      you: "tu",
      displayName: "nome visibile",
      displayNamePlaceholder: "come ti salutiamo",
      language: "lingua",
      languageNote: "Salvato nel tuo account — l'assistente risponde comunque nella lingua in cui scrivi.",
      save: "salva",
      promoter: "promoter",
      promoterNote: "Ciò che gestisci. Gli eventi inviati sono comunque collegati a te.",
      becomePromoter: "pubblica le tue serate",
      becomePromoterNote: "Dicci cosa gestisci e questo account diventa da promoter — potrai pubblicare subito.",
      becomePromoterCta: "diventa promoter",
      becamePromoter: "ora sei un promoter — puoi pubblicare",
      organisation: "organizzazione",
      organisationPlaceholder: "locale, etichetta, collettivo…",
      website: "sito web",
      phone: "telefono",
      venues: "locali che gestisci",
      artists: "artisti che gestisci",
      add: "aggiungi",
      remove: (item) => `rimuovi ${item}`,
      profileSaved: "profilo salvato",
      promoterSaved: "dati promoter salvati",
      saveFailed: "impossibile salvare",
      orgRequired: "il nome dell'organizzazione è obbligatorio",
    },
    pro: {
      needsPro: "Per pubblicare eventi serve un account promoter.",
      becomeProLink: "inserisci i tuoi dati da promoter e pubblica →",
      signInLink: "accedi →",
      onboardingSteps: [
        "Trascina un volantino, un PDF o una foto — oppure scrivilo, o dillo a voce.",
        "laiive lo legge e compila il modulo. Ogni campo è tuo da correggere.",
        "Conferma, e l'evento è pubblicato.",
        "Chi cerca su laiive una serata come la tua la trova.",
      ],
      onboardingDismiss: "non mostrare più",
      statusExtracting: "leggo quello che hai inviato…",
      readingFile: (name) => `leggo ${name}…`,
      notPromoter: "Il tuo account non è ancora un account promoter.",
      genericError: "Qualcosa è andato storto",
      couldNotRead: "Impossibile leggere quel file",
      published: (name) => `Pubblicato — ${name} è online`,
      publishedMarker: (name, k, n) => `Ho pubblicato "${name}" (evento ${k} di ${n}).`,
      walkComplete: (n) =>
        n > 1
          ? `Tutti e ${n} gli eventi sono online su laiive. Invia un altro elenco quando vuoi.`
          : `Il tuo evento è online su laiive. Invia un altro elenco quando vuoi.`,
      alreadyExists: "Quell'evento è già su laiive.",
      publishFailed: "Impossibile pubblicare",
      eventOf: (k, n) => `evento ${k} di ${n}`,
      attach: "Allega un volantino, un documento o una registrazione",
      send: "Invia",
      placeholder: "artista, locale, data, prezzo…",
    },
    form: {
      title: "dettagli dell'evento",
      stillNeeded: (n) => (n === 1 ? "ne manca 1" : `ne mancano ${n}`),
      labels: {
        name: "nome dell'evento",
        artists: "artisti",
        start_at: "inizia",
        venue: "locale",
        address: "indirizzo",
        city: "città",
        price_min: "prezzo da",
        price_max: "prezzo fino a",
        price_currency: "valuta",
        genre: "genere",
        ticket_url: "link biglietti",
        description: "descrizione",
      },
      missingPlaceholder: "l'assistente non è riuscito a trovarlo",
      ticketNoteAria: "informazioni sul link dei biglietti",
      ticketNote:
        "laiive non vende ancora biglietti — questo link porta direttamente dove li vendi già. La vendita qui arriverà.",
      ticketInvalid: "non sembra un indirizzo web",
      publish: "pubblica su laiive",
      publishing: "pubblico…",
      fillHint: (fields) => `completa ${fields} — scrivendo qui o dicendolo all'assistente`,
      addArtist: "+ aggiungi artista",
      removeArtist: "rimuovi artista",
      artistPlaceholder: "nome dell'artista o del gruppo",
      addressOnFile: "registrato su laiive",
      venueSuggestionsAria: "locali che laiive già conosce",
    },
    cards: {
      free: "gratis",
      readMore: "+ leggi di più",
      less: "− meno",
      map: "mappa",
      hideMap: "nascondi mappa",
      openMaps: "apri in Google Maps",
      approximate: "Approssimativo — l'indirizzo esatto di questo locale non è ancora noto.",
      tickets: "biglietti",
      save: "salva",
      saved: "salvato",
      webAria: "Da dove arriva?",
      webSourceFallback: "vedi l'annuncio originale",
      webClaim:
        "Organizzi tu questa serata? Aggiungila da un account promoter e potrai correggerla tu.",
      verifiedAria: "Chi lo ha confermato?",
      verifiedTitle:
        "Confermato da un promoter di questo evento, dal suo account: orario, prezzo e ingresso sono quelli che ha inserito.",
      webTitle:
        "Abbiamo trovato questo annuncio con la nostra ricerca sul web. Il promoter non lo ha confermato, quindi ciò che la pagina non diceva resta vuoto invece di essere inventato.",
      webMissing: "Non indicato sulla pagina",
      fieldTime: "orario di inizio",
      fieldPrice: "prezzo",
      fieldLocation: "indirizzo esatto",
    },
    savedPage: {
      title: "salvati",
      empty: "Non hai ancora salvato niente.",
      emptyHint: "Salva una scheda e ti aspetta qui.",
      upcoming: "in arrivo",
      past: "già passati",
      failed: "non è stato possibile caricare i salvati",
      retry: "riprova",
      back: "indietro",
    },
    menu: {
      account: "account",
      signOut: "esci",
      signIn: "accedi",
      settings: "impostazioni",
      pro: "laiive pro",
      toLaiive: "torna a laiive",
      saved: "salvati",
      aria: "Menu account",
    },
    voice: {
      speak: "Parla invece di scrivere",
      stop: "Ferma e trascrivi",
      denied: "Permesso microfono negato",
      nothing: "Non è arrivato nulla — dillo di nuovo",
      failed: "Trascrizione non riuscita",
    },
    notFound: {
      back: "torna alla chat →",
    },
  },
  ca: {
    chat: {
      placeholder: "cerca el teu esdeveniment aquí…",
      statusReading: "llegint la teva pregunta…",
      statusSearching: "cercant esdeveniments…",
      examples: [
        "concerts de rock aquest cap de setmana a prop meu",
        "concerts avui a prop meu",
        "concerts de rock aquesta setmana a Torí",
      ],
      statusWriting: "escrivint…",
      rateLimited: "Estàs enviant missatges molt ràpid — espera un minut.",
      rateLimitedAnon: "Aquest és el límit gratuït per ara. [Inicia sessió →](/auth) per a un límit més alt.",
      sessionExpired: "La teva sessió ha caducat. [Torna a iniciar sessió →](/auth)",
      genericError: "Alguna cosa ha anat malament.",
      stop: "Atura",
      send: "Envia",
      feedbackDown: "Poc útil",
      feedbackReasonPlaceholder: "Què ha fallat? (opcional)",
      feedbackThanks: "Gràcies pel feedback",
    },
    auth: {
      signInTitle: "inicia sessió",
      signUpTitle: "crea un compte",
      displayNamePlaceholder: "nom visible (opcional)",
      emailPlaceholder: "correu",
      passwordPlaceholder: "contrasenya", // pragma: allowlist secret
      signIn: "inicia sessió",
      signUp: "registra't",
      or: "o",
      google: "continua amb google",
      toSignUp: "sense compte? registra't",
      toSignIn: "ja tens compte? inicia sessió",
      withoutAccount: "continua sense compte →",
      checkInbox: "Revisa el correu per confirmar l'adreça i després inicia sessió.",
      finishing: "completant l'inici de sessió…",
      orgPlaceholder: "organització — sala, segell, col·lectiu…",
      orgRequired: "el nom de l'organització és obligatori",
      promoterSetupFailed: "Compte creat, però l'alta de promotor no s'ha completat — afegeix-la al teu compte.",
      promoterSessionStale: "Ja ets promotor, però aquesta sessió encara és l'anterior — torna a iniciar sessió per obrir pro.",
      failed: "No s'ha pogut iniciar la sessió",
      googleFailed: "No s'ha pogut iniciar la sessió amb Google",
      proInvite: "promotor, músic, propietari d'una sala?",
      proCta: "registra't com a pro — gratis, i les teves nits entren directes a laiive →",
    },
    account: {
      back: "enrere",
      title: "compte",
      you: "tu",
      displayName: "nom visible",
      displayNamePlaceholder: "com et saludem",
      language: "idioma",
      languageNote: "Es desa al teu compte — l'assistent segueix responent en l'idioma en què escriguis.",
      save: "desa",
      promoter: "promotor",
      promoterNote: "El que gestiones. Els esdeveniments enviats es vinculen a tu igualment.",
      becomePromoter: "publica les teves nits",
      becomePromoterNote: "Digues-nos què gestiones i aquest compte passa a ser de promotor — podràs publicar de seguida.",
      becomePromoterCta: "fes-te promotor",
      becamePromoter: "ja ets promotor — pots publicar",
      organisation: "organització",
      organisationPlaceholder: "sala, segell, col·lectiu…",
      website: "web",
      phone: "telèfon",
      venues: "sales que gestiones",
      artists: "artistes que gestiones",
      add: "afegeix",
      remove: (item) => `treu ${item}`,
      profileSaved: "perfil desat",
      promoterSaved: "dades de promotor desades",
      saveFailed: "no s'ha pogut desar",
      orgRequired: "el nom de l'organització és obligatori",
    },
    pro: {
      needsPro: "Per publicar esdeveniments cal un compte de promotor.",
      becomeProLink: "configura les teves dades de promotor i publica →",
      signInLink: "inicia sessió →",
      onboardingSteps: [
        "Deixa-hi un cartell, un PDF o una foto — o escriu-ho, o digues-ho en veu alta.",
        "laiive ho llegeix i omple el formulari. Tots els camps són teus per corregir.",
        "Confirma, i l'esdeveniment ja hi és.",
        "Qui busqui a laiive una nit com la teva la troba.",
      ],
      onboardingDismiss: "no ho tornis a mostrar",
      statusExtracting: "llegint el que has enviat…",
      readingFile: (name) => `llegint ${name}…`,
      notPromoter: "El teu compte encara no és de promotor.",
      genericError: "Alguna cosa ha anat malament",
      couldNotRead: "No s'ha pogut llegir aquest fitxer",
      published: (name) => `Publicat — ${name} ja és a laiive`,
      publishedMarker: (name, k, n) => `He publicat "${name}" (esdeveniment ${k} de ${n}).`,
      walkComplete: (n) =>
        n > 1
          ? `Els ${n} esdeveniments ja són a laiive. Envia un altre llistat quan vulguis.`
          : `El teu esdeveniment ja és a laiive. Envia un altre llistat quan vulguis.`,
      alreadyExists: "Aquest esdeveniment ja és a laiive.",
      publishFailed: "No s'ha pogut publicar",
      eventOf: (k, n) => `esdeveniment ${k} de ${n}`,
      attach: "Adjunta un cartell, document o gravació",
      send: "Envia",
      placeholder: "artista, sala, data, preu…",
    },
    form: {
      title: "detalls de l'esdeveniment",
      stillNeeded: (n) => (n === 1 ? "en falta 1" : `en falten ${n}`),
      labels: {
        name: "nom de l'esdeveniment",
        artists: "artistes",
        start_at: "comença",
        venue: "sala",
        address: "adreça",
        city: "ciutat",
        price_min: "preu des de",
        price_max: "preu fins a",
        price_currency: "moneda",
        genre: "gènere",
        ticket_url: "enllaç d'entrades",
        description: "descripció",
      },
      missingPlaceholder: "l'assistent no ho ha pogut trobar",
      ticketNoteAria: "sobre l'enllaç d'entrades",
      ticketNote:
        "laiive encara no ven entrades — aquest enllaç porta directament on ja les vens. La venda aquí arribarà.",
      ticketInvalid: "això no sembla una adreça web",
      publish: "publica a laiive",
      publishing: "publicant…",
      fillHint: (fields) => `omple ${fields} — escrivint aquí o dient-ho a l'assistent`,
      addArtist: "+ afegir artista",
      removeArtist: "treure artista",
      artistPlaceholder: "nom de l'artista o del grup",
      addressOnFile: "registrada a laiive",
      venueSuggestionsAria: "sales que laiive ja coneix",
    },
    cards: {
      free: "gratuït",
      readMore: "+ llegeix més",
      less: "− menys",
      map: "mapa",
      hideMap: "amaga el mapa",
      openMaps: "obre a Google Maps",
      approximate: "Aproximat — encara no es coneix l'adreça exacta d'aquesta sala.",
      tickets: "entrades",
      save: "desa",
      saved: "desat",
      webAria: "D'on surt això?",
      webSourceFallback: "veure l'anunci original",
      webClaim:
        "Organitzes aquesta nit? Afegeix-la des d'un compte de promotor i podràs corregir-la tu.",
      verifiedAria: "Qui ho ha confirmat?",
      verifiedTitle:
        "Confirmat per un promotor d'aquest esdeveniment, des del seu compte: l'hora, el preu i la porta són els que va indicar.",
      webTitle:
        "Hem trobat aquest anunci amb la nostra cerca web. El promotor no l'ha confirmat, així que allò que la pàgina no deia es deixa en blanc en lloc d'inventar-ho.",
      webMissing: "La pàgina no ho indicava",
      fieldTime: "hora d'inici",
      fieldPrice: "preu",
      fieldLocation: "adreça exacta",
    },
    savedPage: {
      title: "desats",
      empty: "Encara no has desat res.",
      emptyHint: "Desa una targeta i t'espera aquí.",
      upcoming: "properament",
      past: "ja han passat",
      failed: "no s'han pogut carregar els desats",
      retry: "torna-ho a provar",
      back: "enrere",
    },
    menu: {
      account: "compte",
      signOut: "tanca la sessió",
      signIn: "inicia sessió",
      settings: "configuració",
      pro: "laiive pro",
      toLaiive: "torna a laiive",
      saved: "desats",
      aria: "Menú del compte",
    },
    voice: {
      speak: "Parla en lloc d'escriure",
      stop: "Atura i transcriu",
      denied: "Sense permís de micròfon",
      nothing: "No ha arribat res — digues-ho una altra vegada",
      failed: "No s'ha pogut transcriure",
    },
    notFound: {
      back: "torna al xat →",
    },
  },
};
