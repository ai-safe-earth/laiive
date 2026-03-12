
<img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/357725b4-4da2-4463-b9a5-896a29fc4b79" />
# Laiive.com

#### what is 🫦Laiive?
laiive is what will save you from being at home scrolling for the rest of your life.
laiive is where you find the perfect life event for you, and if you are an artist or a promoter is the way to make people know you are doing something.
If you want to do something now, friday evening, saturday morning... Just ask, Laiive will help you to find what you are looking for outside of the screen.

![mockup](https://github.com/user-attachments/assets/4f94c5df-6b66-42b8-9925-1314b9987c48)

#### why is 🫦laiive needed?
laiive links the broken connection between events and public[^*]

![mission](https://github.com/user-attachments/assets/569506fc-6adb-4762-8b60-2f2e0bb69866)

#### 🫦laiive look for all, not just for the big ones

laiive was born to connect small events with people close to them, laiive does not focus on big musical events as many platforms are, laiive works on the human and community scale where small music events live.

#### 🫦laiive uses AI to balance our digital-physical culture.  

laiive was born as an AI cultural agenda, with the AI hype and AI competition without the AI Safety layer laiive has become a subversive way of using AI, it tries to steal attention from the main digital platforms and bring it back to real world social meetings. laiive positions itself as an ethical AI app helping to develop a balanced digital-physical culture before the intermediate layer in our digital comunication becomes too powerful.

#### 🫦laiive has abitious positive outcomes

laiive is a catalyst of a worldwide demand that is actually unattended. laiive connects thousands of daily live events and millions of people are not going to them because they don't know they exist. Solving this gap may have a direct positive outcome, and many indirect ones, the most interesting one for our point of view, and because of the times that we are facing, is that laiive can enhance community strengths around physical cultural events, historically relevant focal points of resistance to authoritarianism. 

---

## Services
<img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  /><img width="90" height="90" alt="laiive1" src="https://github.com/user-attachments/assets/f8dc0267-f630-4a87-b3f8-fe0277137ba5"  />
### UI
a simple and accessible UI is the public view of laiive, easy to publish an event, easy to find an event.

### Retriever Agent
The backbone of laiive, an agent-based retrieval system with high accuracy on retrievals from the Neo4j knowledge graph database. The retriever uses an orchestrator pattern with specialized tools.

Currently supports session-based queries. User ID preferences support planned for future phases.

### Pusher Agent
Multimodal event ingestion service that receives submissions (text/image/audio), runs router + extraction + guardrails + HITL (Human-In-The-Loop) validation. The system takes care of reliability and data quality through automated validation and human review workflows.

### Internet search tool (previous Event Scraper - Legacy)
Internet search service for complementary data feed. The tool will help the main data source (promoters publications) as the system transitions based on geographic penetration. 

### Data Strategy
laiive deals with ephemeral data, data that still doesn't exist. laiive is a systemic platform that generates dynamic processes, it grows in inertia when users use it and promoters do too. Neo4j graph database is the heart of this dynamics and stores all the system knowledge, enabling natural relationship queries between events, artists, venues, and users.

---

## License

This project is licensed under the **Apache License 2.0** - see the [LICENSE](LICENSES/LICENSE) file for details.

---

### instructions

#### Development Setup in devcontainer (recommended)

1. Open the devcontainer: (instructions for VScode/Cursor)
   ```bash
   # From the root directory
   code .
   # Then click "Reopen in Container" when prompted
   ```
   alternatively Ctrl+shift+P "DevContainer: Rebuild and reopen in Container"

2. Navigate to desired service directory and install dependencies (once inside the devcontainer):
   ```bash
   cd services/<service-name>
   uv sync  # Install Python dependencies using uv
   ```
   alternatively use the Makefile command
   ```bash
   make deps
   ```

3. The containers start automatically, but to run the actual services:
   ```bash
   make run-dev  # Start frontend and backend services
   ```

4. Open localhost:3001 and localhost:8001 to check or use the services ports. (they are maped from port 3000 to port 3001 and from port 8000 to port 8001 in the devcontainer)


#### Production Setup (it build and runs all the services at once)

1. Go to the root directory and run:
   ```bash
   make up-prod
   ```
