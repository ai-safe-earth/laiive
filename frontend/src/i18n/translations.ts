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
    welcome: string;
    promoterLink: string;
    placeholder: string;
    statusReading: string;
    statusSearching: string;
    statusWriting: string;
    rateLimited: string;
    rateLimitedAnon: string; // markdown, links to /auth
    sessionExpired: string; // markdown, links to /auth
    genericError: string;
    stop: string;
    send: string;
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
    failed: string;
    googleFailed: string;
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
    contactUs: string;
    signInLink: string;
    emptyTitle: string;
    emptyHint: string;
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
    publish: string;
    publishing: string;
    fillHint: (fields: string) => string;
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
    web: string;
    webTitle: string;
  };
  menu: {
    account: string;
    signOut: string;
    signIn: string;
    aria: string;
  };
  notFound: {
    back: string;
  };
}

export const translations: Record<Language, Translations> = {
  en: {
    chat: {
      welcome: "Hey! 👋 I'm here to help you discover amazing live music events near you. What are you in the mood for today?",
      promoterLink: "promoter/musician →",
      placeholder: "Tell me what you're looking for...",
      statusReading: "reading your question…",
      statusSearching: "searching the graph…",
      statusWriting: "writing…",
      rateLimited: "You are sending requests a little fast — give it a minute.",
      rateLimitedAnon: "That's the free quota for now. [Sign in →](/auth) for a higher limit.",
      sessionExpired: "Your session expired. [Sign in again →](/auth)",
      genericError: "Something went wrong.",
      stop: "Stop",
      send: "Send",
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
      failed: "Authentication failed",
      googleFailed: "Google sign-in failed",
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
      promoterNote: "What you run. Submitted events are linked to you regardless; this is context, not a permission.",
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
      contactUs: "signed in without pro access — contact us",
      signInLink: "sign in →",
      emptyTitle: "Tell me about your event — type it, say it, or drop a flyer.",
      emptyHint: "photo · PDF · Word · voice — all of it becomes the same form",
      statusExtracting: "reading what you sent…",
      readingFile: (name) => `reading ${name}…`,
      notPromoter: "Your account is not a promoter account yet.",
      genericError: "Something went wrong",
      couldNotRead: "Could not read that file",
      published: (name) => `Published — ${name} is live`,
      publishedMarker: (name, k, n) => `Published "${name}" (event ${k} of ${n}).`,
      walkComplete: (n) =>
        n > 1
          ? `All ${n} events are live on laiive. 🎉 Send another listing whenever you're ready.`
          : `Your event is live on laiive. 🎉 Send another listing whenever you're ready.`,
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
        artists: "artists (comma separated)",
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
      publish: "publish to laiive",
      publishing: "publishing…",
      fillHint: (fields) => `fill ${fields} — by typing here or just telling the assistant`,
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
      web: "web",
      webTitle: "Found on the internet, not submitted by the promoter",
    },
    menu: {
      account: "account",
      signOut: "sign out",
      signIn: "sign in",
      aria: "Account menu",
    },
    notFound: {
      back: "back to the chat →",
    },
  },
  es: {
    chat: {
      welcome: "¡Hola! 👋 Estoy aquí para ayudarte a descubrir increíbles eventos de música en vivo cerca de ti. ¿Qué te apetece hoy?",
      promoterLink: "promotor/músico →",
      placeholder: "Dime qué estás buscando...",
      statusReading: "leyendo tu pregunta…",
      statusSearching: "buscando en el grafo…",
      statusWriting: "escribiendo…",
      rateLimited: "Estás enviando mensajes muy rápido — dale un minuto.",
      rateLimitedAnon: "Ese es el límite gratuito por ahora. [Inicia sesión →](/auth) para un límite mayor.",
      sessionExpired: "Tu sesión ha caducado. [Vuelve a iniciar sesión →](/auth)",
      genericError: "Algo ha ido mal.",
      stop: "Detener",
      send: "Enviar",
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
      failed: "No se pudo iniciar sesión",
      googleFailed: "No se pudo iniciar sesión con Google",
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
      promoterNote: "Lo que gestionas. Los eventos enviados se vinculan a ti igualmente; esto es contexto, no un permiso.",
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
      contactUs: "sesión iniciada sin acceso pro — contáctanos",
      signInLink: "inicia sesión →",
      emptyTitle: "Cuéntame tu evento — escríbelo, dilo o suelta un cartel.",
      emptyHint: "foto · PDF · Word · voz — todo acaba en el mismo formulario",
      statusExtracting: "leyendo lo que has enviado…",
      readingFile: (name) => `leyendo ${name}…`,
      notPromoter: "Tu cuenta aún no es de promotor.",
      genericError: "Algo ha ido mal",
      couldNotRead: "No se pudo leer ese archivo",
      published: (name) => `Publicado — ${name} ya está en laiive`,
      publishedMarker: (name, k, n) => `He publicado "${name}" (evento ${k} de ${n}).`,
      walkComplete: (n) =>
        n > 1
          ? `Los ${n} eventos ya están en laiive. 🎉 Envía otro listado cuando quieras.`
          : `Tu evento ya está en laiive. 🎉 Envía otro listado cuando quieras.`,
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
        artists: "artistas (separados por comas)",
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
      publish: "publicar en laiive",
      publishing: "publicando…",
      fillHint: (fields) => `rellena ${fields} — escribiendo aquí o diciéndoselo al asistente`,
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
      web: "web",
      webTitle: "Encontrado en internet, no enviado por el promotor",
    },
    menu: {
      account: "cuenta",
      signOut: "cerrar sesión",
      signIn: "inicia sesión",
      aria: "Menú de cuenta",
    },
    notFound: {
      back: "volver al chat →",
    },
  },
  it: {
    chat: {
      welcome: "Ciao! 👋 Sono qui per aiutarti a scoprire fantastici eventi di musica dal vivo vicino a te. Cosa ti va oggi?",
      promoterLink: "promoter/musicista →",
      placeholder: "Dimmi cosa stai cercando...",
      statusReading: "leggo la tua domanda…",
      statusSearching: "cerco nel grafo…",
      statusWriting: "scrivo…",
      rateLimited: "Stai inviando richieste un po' troppo in fretta — aspetta un minuto.",
      rateLimitedAnon: "Questo è il limite gratuito per ora. [Accedi →](/auth) per un limite più alto.",
      sessionExpired: "La tua sessione è scaduta. [Accedi di nuovo →](/auth)",
      genericError: "Qualcosa è andato storto.",
      stop: "Interrompi",
      send: "Invia",
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
      failed: "Autenticazione non riuscita",
      googleFailed: "Accesso con Google non riuscito",
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
      promoterNote: "Ciò che gestisci. Gli eventi inviati sono comunque collegati a te; questo è contesto, non un permesso.",
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
      contactUs: "accesso senza permessi pro — contattaci",
      signInLink: "accedi →",
      emptyTitle: "Raccontami il tuo evento — scrivilo, dillo o trascina un volantino.",
      emptyHint: "foto · PDF · Word · voce — tutto diventa lo stesso modulo",
      statusExtracting: "leggo quello che hai inviato…",
      readingFile: (name) => `leggo ${name}…`,
      notPromoter: "Il tuo account non è ancora un account promoter.",
      genericError: "Qualcosa è andato storto",
      couldNotRead: "Impossibile leggere quel file",
      published: (name) => `Pubblicato — ${name} è online`,
      publishedMarker: (name, k, n) => `Ho pubblicato "${name}" (evento ${k} di ${n}).`,
      walkComplete: (n) =>
        n > 1
          ? `Tutti e ${n} gli eventi sono online su laiive. 🎉 Invia un altro elenco quando vuoi.`
          : `Il tuo evento è online su laiive. 🎉 Invia un altro elenco quando vuoi.`,
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
        artists: "artisti (separati da virgole)",
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
      publish: "pubblica su laiive",
      publishing: "pubblico…",
      fillHint: (fields) => `completa ${fields} — scrivendo qui o dicendolo all'assistente`,
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
      web: "web",
      webTitle: "Trovato su internet, non inviato dal promoter",
    },
    menu: {
      account: "account",
      signOut: "esci",
      signIn: "accedi",
      aria: "Menu account",
    },
    notFound: {
      back: "torna alla chat →",
    },
  },
  ca: {
    chat: {
      welcome: "Hola! 👋 Estic aquí per ajudar-te a descobrir increïbles esdeveniments de música en directe a prop teu. Què t'agradaria avui?",
      promoterLink: "promotor/músic →",
      placeholder: "Digues-me què estàs buscant...",
      statusReading: "llegint la teva pregunta…",
      statusSearching: "cercant al graf…",
      statusWriting: "escrivint…",
      rateLimited: "Estàs enviant missatges molt ràpid — espera un minut.",
      rateLimitedAnon: "Aquest és el límit gratuït per ara. [Inicia sessió →](/auth) per a un límit més alt.",
      sessionExpired: "La teva sessió ha caducat. [Torna a iniciar sessió →](/auth)",
      genericError: "Alguna cosa ha anat malament.",
      stop: "Atura",
      send: "Envia",
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
      failed: "No s'ha pogut iniciar la sessió",
      googleFailed: "No s'ha pogut iniciar la sessió amb Google",
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
      promoterNote: "El que gestiones. Els esdeveniments enviats es vinculen a tu igualment; això és context, no un permís.",
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
      contactUs: "sessió iniciada sense accés pro — contacta'ns",
      signInLink: "inicia sessió →",
      emptyTitle: "Explica'm el teu esdeveniment — escriu-lo, digues-lo o deixa-hi un cartell.",
      emptyHint: "foto · PDF · Word · veu — tot acaba al mateix formulari",
      statusExtracting: "llegint el que has enviat…",
      readingFile: (name) => `llegint ${name}…`,
      notPromoter: "El teu compte encara no és de promotor.",
      genericError: "Alguna cosa ha anat malament",
      couldNotRead: "No s'ha pogut llegir aquest fitxer",
      published: (name) => `Publicat — ${name} ja és a laiive`,
      publishedMarker: (name, k, n) => `He publicat "${name}" (esdeveniment ${k} de ${n}).`,
      walkComplete: (n) =>
        n > 1
          ? `Els ${n} esdeveniments ja són a laiive. 🎉 Envia un altre llistat quan vulguis.`
          : `El teu esdeveniment ja és a laiive. 🎉 Envia un altre llistat quan vulguis.`,
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
        artists: "artistes (separats per comes)",
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
      publish: "publica a laiive",
      publishing: "publicant…",
      fillHint: (fields) => `omple ${fields} — escrivint aquí o dient-ho a l'assistent`,
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
      web: "web",
      webTitle: "Trobat a internet, no enviat pel promotor",
    },
    menu: {
      account: "compte",
      signOut: "tanca la sessió",
      signIn: "inicia sessió",
      aria: "Menú del compte",
    },
    notFound: {
      back: "torna al xat →",
    },
  },
};
