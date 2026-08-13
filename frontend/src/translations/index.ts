export type Language = 'en' | 'es' | 'it' | 'ca';

export interface Translations {
  // Chat page
  chat: {
    welcome: string;
    promoterLink: string;
    placeholder: string;
  };
  // Promoter page
  promoter: {
    title: string;
    subtitle: string;
    videoPlaceholder: string;
    videoDescription: string;
    ctaButton: string;
    learnMore: string;
    moreAboutLaiive: string;
    welcomeTitle: string;
    welcomeText: string;
    backToUser: string;
  };
  // About page
  about: {
    title: string;
    subtitle: string;
    philosophyTitle: string;
    philosophyText: string;
    aiEthicsTitle: string;
    aiEthicsText: string;
    smallVenuesTitle: string;
    smallVenuesText: string;
    joinTitle: string;
    joinText: string;
    joinInstructionsTitle: string;
    joinStep1: string;
    joinStep2: string;
    joinStep3: string;
    joinStep3Link: string;
    joinStep4: string;
    back: string;
  };
  // Language selector
  language: {
    label: string;
  };
  // Promoter create page
  promoterCreate: {
    welcome: string;
    placeholder: string;
  };
}

export const translations: Record<Language, Translations> = {
  en: {
    chat: {
      welcome: "Hey! 👋 I'm here to help you discover amazing live music events near you. What are you in the mood for today?",
      promoterLink: "promoter/musician →",
      placeholder: "Tell me what you're looking for...",
    },
    promoter: {
      title: "Small stages. Big connections.",
      subtitle: "Share your events with thousands of music lovers",
      videoPlaceholder: "Walkthrough video placeholder",
      videoDescription: "Video will be embedded here",
      ctaButton: "Push your event now",
      learnMore: "Learn more about the project →",
      moreAboutLaiive: "more about laiive →",
      welcomeTitle: "help laiive to lead a cultural revolution 🎵🎵🎵",
      welcomeText: "Your feedback is valuable to us. Tell us how we can help you build a community around your events.",
      backToUser: "← public app",
    },
    about: {
      title: "Laiive is not a social network!!!",
      subtitle: "Quite the opposite, laiive is an enabler of decentralized community networks built around live music and cultural events.",
      philosophyTitle: "Our Philosophy",
      philosophyText: "Laiive is not a social network. It enables social networks around live cultural events. We believe live music is the heartbeat of local communities. Small venues, emerging artists, and independent promoters deserve the same visibility as major events. Our platform connects passionate music lovers with authentic live experiences, making it easier to discover what's happening in your neighborhood.",
      aiEthicsTitle: "AI Ethics Layer",
      aiEthicsText: "AI in laiive is not a product—it's an enabler. It exists to back the platform's real purpose: connecting people through live cultural experiences. Ethics are not applied as guardrails after the fact; they are foundational and scalable, built into everything we do from day one. This is an ethical project at scale, where transparency, fairness, and community benefit are not constraints but core architecture.",
      smallVenuesTitle: "Why Small Venues Matter",
      smallVenuesText: "Small venues are where legends are born. They're where communities gather, where new sounds emerge, and where music stays real. But they often struggle with visibility and marketing. We're building tools to amplify their voice without changing their soul. By making event discovery smarter and more accessible, we help keep local music scenes alive and thriving.",
      joinTitle: "Join the Movement",
      joinText: "As an early partner, you're helping us shape the future of live music discovery. Your feedback, your events, and your community make this platform what it is. Together, we're creating something that puts people and music first—not algorithms and advertising.",
      joinInstructionsTitle: "Instructions to change the world:",
      joinStep1: "If you are a musician, a promoter, a venue owner or an event organizer... do your pro account (it's free forever).",
      joinStep2: "Upload your events",
      joinStep3: "Spread the word, tell your friends, colleagues, print",
      joinStep3Link: "this",
      joinStep4: "and paste it to your local door, your car, your guitar, your battery. Enjoy!!! Use it, and go to a good concert!!",
      back: "← back",
    },
    language: {
      label: "Language",
    },
    promoterCreate: {
      welcome: "Hi! Tell me about your event and I'll help you publish it on laiive.",
      placeholder: "Describe your event...",
    },
  },
  es: {
    chat: {
      welcome: "¡Hola! 👋 Estoy aquí para ayudarte a descubrir increíbles eventos de música en vivo cerca de ti. ¿Qué te apetece hoy?",
      promoterLink: "promotor/músico →",
      placeholder: "Dime qué estás buscando...",
    },
    promoter: {
      title: "Escenarios pequeños. Grandes conexiones.",
      subtitle: "Comparte tus eventos con miles de amantes de la música",
      videoPlaceholder: "Marcador de video tutorial",
      videoDescription: "El video se incrustará aquí",
      ctaButton: "Publica tu evento ahora",
      learnMore: "Más información sobre el proyecto →",
      moreAboutLaiive: "más sobre laiive →",
      welcomeTitle: "ayuda a laiive a liderar una revolución cultural 🎵🎵🎵",
      welcomeText: "Tu feedback es valioso para nosotros. Cuéntanos cómo podemos ayudarte a construir una comunidad alrededor de tus eventos.",
      backToUser: "← app pública",
    },
    about: {
      title: "Laiive no es una red social!!!",
      subtitle: "Todo lo contrario, laiive es un habilitador de redes comunitarias descentralizadas construidas alrededor de la música en vivo y eventos culturales.",
      philosophyTitle: "Nuestra Filosofía",
      philosophyText: "Laiive no es una red social. Permite crear redes sociales alrededor de eventos culturales en vivo. Creemos que la música en vivo es el corazón de las comunidades locales. Los lugares pequeños, artistas emergentes y promotores independientes merecen la misma visibilidad que los grandes eventos. Nuestra plataforma conecta amantes apasionados de la música con experiencias auténticas en vivo.",
      aiEthicsTitle: "Capa de Ética de IA",
      aiEthicsText: "La IA en laiive no es un producto, es un facilitador. Existe para respaldar el verdadero propósito de la plataforma: conectar personas a través de experiencias culturales en vivo. La ética no se aplica como barandillas después del hecho; es fundacional y escalable, integrada en todo lo que hacemos desde el primer día. Este es un proyecto ético a escala, donde la transparencia, la equidad y el beneficio comunitario no son restricciones sino arquitectura central.",
      smallVenuesTitle: "Por Qué Importan los Lugares Pequeños",
      smallVenuesText: "Los lugares pequeños son donde nacen las leyendas. Son donde las comunidades se reúnen, donde emergen nuevos sonidos y donde la música se mantiene real. Pero a menudo luchan con visibilidad y marketing. Estamos construyendo herramientas para amplificar su voz sin cambiar su alma. Al hacer el descubrimiento de eventos más inteligente y accesible, ayudamos a mantener vivas las escenas musicales locales.",
      joinTitle: "Únete al Movimiento",
      joinText: "Como socio fundador, estás ayudándonos a dar forma al futuro del descubrimiento de música en vivo. Tu feedback, tus eventos y tu comunidad hacen que esta plataforma sea lo que es. Juntos, estamos creando algo que pone a las personas y la música primero, no algoritmos y publicidad.",
      joinInstructionsTitle: "Instrucciones para cambiar el mundo:",
      joinStep1: "Si eres músico, promotor, dueño de un local o organizador de eventos... crea tu cuenta pro (es gratis para siempre).",
      joinStep2: "Sube tus eventos",
      joinStep3: "Corre la voz, cuéntaselo a tus amigos, colegas, imprime",
      joinStep3Link: "esto",
      joinStep4: "y pégalo en tu puerta local, tu coche, tu guitarra, tu batería. ¡¡¡Disfruta!!! Úsalo, ¡y ve a un buen concierto!!",
      back: "← atrás",
    },
    language: {
      label: "Idioma",
    },
    promoterCreate: {
      welcome: "¡Hola! Cuéntame sobre tu evento y te ayudaré a publicarlo en laiive.",
      placeholder: "Describe tu evento...",
    },
  },
  it: {
    chat: {
      welcome: "Ciao! 👋 Sono qui per aiutarti a scoprire fantastici eventi di musica dal vivo vicino a te. Cosa ti va oggi?",
      promoterLink: "promoter/musicista →",
      placeholder: "Dimmi cosa stai cercando...",
    },
    promoter: {
      title: "Piccoli palchi. Grandi connessioni.",
      subtitle: "Condividi i tuoi eventi con migliaia di amanti della musica",
      videoPlaceholder: "Segnaposto video tutorial",
      videoDescription: "Il video sarà incorporato qui",
      ctaButton: "Pubblica il tuo evento ora",
      learnMore: "Scopri di più sul progetto →",
      moreAboutLaiive: "più su laiive →",
      welcomeTitle: "aiuta laiive a guidare una rivoluzione culturale 🎵🎵🎵",
      welcomeText: "Il tuo feedback è prezioso per noi. Raccontaci come possiamo aiutarti a costruire una comunità attorno ai tuoi eventi.",
      backToUser: "← app pubblica",
    },
    about: {
      title: "Laiive non è un social network!!!",
      subtitle: "Anzi, al contrario, laiive è un abilitatore di reti comunitarie decentralizzate costruite attorno alla musica dal vivo e agli eventi culturali.",
      philosophyTitle: "La Nostra Filosofia",
      philosophyText: "Laiive non è un social network. Abilita reti sociali attorno a eventi culturali dal vivo. Crediamo che la musica dal vivo sia il battito del cuore delle comunità locali. I piccoli locali, gli artisti emergenti e i promoter indipendenti meritano la stessa visibilità dei grandi eventi. La nostra piattaforma connette gli amanti appassionati della musica con esperienze autentiche dal vivo.",
      aiEthicsTitle: "Livello di Etica dell'IA",
      aiEthicsText: "L'IA in laiive non è un prodotto, è un abilitatore. Esiste per supportare il vero scopo della piattaforma: connettere le persone attraverso esperienze culturali dal vivo. L'etica non viene applicata come guardrail a posteriori; è fondamentale e scalabile, integrata in tutto ciò che facciamo dal primo giorno. Questo è un progetto etico su scala, dove trasparenza, equità e beneficio per la comunità non sono vincoli ma architettura centrale.",
      smallVenuesTitle: "Perché i Piccoli Locali Contano",
      smallVenuesText: "I piccoli locali sono dove nascono le leggende. Sono dove le comunità si riuniscono, dove emergono nuovi suoni e dove la musica rimane vera. Ma spesso lottano con visibilità e marketing. Stiamo costruendo strumenti per amplificare la loro voce senza cambiare la loro anima. Rendendo la scoperta di eventi più intelligente e accessibile, aiutiamo a mantenere vive le scene musicali locali.",
      joinTitle: "Unisciti al Movimento",
      joinText: "Come partner iniziale, stai aiutandoci a plasmare il futuro della scoperta di musica dal vivo. Il tuo feedback, i tuoi eventi e la tua comunità rendono questa piattaforma ciò che è. Insieme, stiamo creando qualcosa che mette le persone e la musica al primo posto, non algoritmi e pubblicità.",
      joinInstructionsTitle: "Istruzioni per cambiare il mondo:",
      joinStep1: "Se sei un musicista, un promoter, un proprietario di locale o un organizzatore di eventi... fai il tuo account pro (è gratis per sempre).",
      joinStep2: "Carica i tuoi eventi",
      joinStep3: "Spargi la voce, dillo ai tuoi amici, colleghi, stampa",
      joinStep3Link: "questo",
      joinStep4: "e attaccalo alla tua porta locale, alla tua macchina, alla tua chitarra, alla tua batteria. Divertiti!!! Usalo, e vai a un bel concerto!!",
      back: "← indietro",
    },
    language: {
      label: "Lingua",
    },
    promoterCreate: {
      welcome: "Ciao! Raccontami del tuo evento e ti aiuterò a pubblicarlo su laiive.",
      placeholder: "Descrivi il tuo evento...",
    },
  },
  ca: {
    chat: {
      welcome: "Hola! 👋 Estic aquí per ajudar-te a descobrir increïbles esdeveniments de música en directe a prop teu. Què t'agradaria avui?",
      promoterLink: "promotor/músic →",
      placeholder: "Digues-me què estàs buscant...",
    },
    promoter: {
      title: "Escenaris petits. Grans connexions.",
      subtitle: "Comparteix els teus esdeveniments amb milers d'amants de la música",
      videoPlaceholder: "Marcador de vídeo tutorial",
      videoDescription: "El vídeo s'inserirà aquí",
      ctaButton: "Publica el teu esdeveniment ara",
      learnMore: "Més informació sobre el projecte →",
      moreAboutLaiive: "més sobre laiive →",
      welcomeTitle: "ajuda laiive a liderar una revolució cultural 🎵🎵🎵",
      welcomeText: "El teu feedback és valuós per a nosaltres. Explica'ns com podem ajudar-te a construir una comunitat al voltant dels teus esdeveniments.",
      backToUser: "← app pública",
    },
    about: {
      title: "Laiive no és una xarxa social!!!",
      subtitle: "Ben al contrari, laiive és un habilitador de xarxes comunitàries descentralitzades construïdes al voltant de la música en directe i esdeveniments culturals.",
      philosophyTitle: "La Nostra Filosofia",
      philosophyText: "Laiive no és una xarxa social. Permet crear xarxes socials al voltant d'esdeveniments culturals en directe. Creiem que la música en directe és el cor de les comunitats locals. Els llocs petits, artistes emergents i promotors independents mereixen la mateixa visibilitat que els grans esdeveniments. La nostra plataforma connecta amants apassionats de la música amb experiències autèntiques en directe.",
      aiEthicsTitle: "Capa d'Ètica d'IA",
      aiEthicsText: "La IA a laiive no és un producte, és un habilitador. Existeix per donar suport al veritable propòsit de la plataforma: connectar persones a través d'experiències culturals en directe. L'ètica no s'aplica com a baranes després del fet; és fonamental i escalable, integrada en tot el que fem des del primer dia. Aquest és un projecte ètic a escala, on la transparència, l'equitat i el benefici comunitari no són restriccions sinó arquitectura central.",
      smallVenuesTitle: "Per Què Importen els Llocs Petits",
      smallVenuesText: "Els llocs petits són on neixen les llegendes. Són on les comunitats es reuneixen, on emergeixen nous sons i on la música es manté real. Però sovint lluiten amb visibilitat i màrqueting. Estem construint eines per amplificar la seva veu sense canviar la seva ànima. Fent el descobriment d'esdeveniments més intel·ligent i accessible, ajudem a mantenir vives les escenes musicals locals.",
      joinTitle: "Uneix-te al Moviment",
      joinText: "Com a soci fundador, estàs ajudant-nos a donar forma al futur del descobriment de música en directe. El teu feedback, els teus esdeveniments i la teva comunitat fan que aquesta plataforma sigui el que és. Junts, estem creant alguna cosa que posa les persones i la música primer, no algorismes i publicitat.",
      joinInstructionsTitle: "Instruccions per canviar el món:",
      joinStep1: "Si ets músic, promotor, propietari d'un local o organitzador d'esdeveniments... fes el teu compte pro (és gratis per sempre).",
      joinStep2: "Puja els teus esdeveniments",
      joinStep3: "Escampa la veu, explica-ho als teus amics, col·legues, imprimeix",
      joinStep3Link: "això",
      joinStep4: "i enganxa-ho a la teva porta local, el teu cotxe, la teva guitarra, la teva bateria. Gaudeix!!! Utilitza-ho, i vés a un bon concert!!",
      back: "← enrere",
    },
    language: {
      label: "Idioma",
    },
    promoterCreate: {
      welcome: "Hola! Explica'm sobre el teu esdeveniment i t'ajudaré a publicar-lo a laiive.",
      placeholder: "Descriu el teu esdeveniment...",
    },
  },
};
