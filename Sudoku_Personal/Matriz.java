public class Matriz {
    public static void inicializarVisitados(int matriz[][], boolean visitados[][]) {
        int N = visitados.length;
        for (int i = 0; i < N; i++) { //Inicializando matriz de visitados
            for (int j = 0; j < N; j++) { //Se marcan como casillas por rellenar aquellas cuyo valor sea 0
                visitados[i][j] = matriz[i][j] != 0;
            }
        }
    }

    public static void printValores(int matriz[][]){
        int N = matriz.length;
        for (int i = 0; i < N; i++) { //Inicializando matriz de visitados
            if ((i) % 3 == 0) System.out.println("______________________________");
            for (int j = 0; j < N; j++){
                if (j % 3 == 0) System.out.print("|");
                System.out.print(" " + matriz[i][j] + " ");
                if (j == N-1) System.out.print("|");
            }
            System.out.println();
            if (i == N-1) System.out.println("______________________________");
        }
    }

    public static void printVisitados (boolean visitados[][]){
        int N = visitados.length;
        for (int i = 0; i < N; i++) { //Inicializando matriz de visitados
            if ((i) % 3 == 0) System.out.println("______________________________");
            for (int j = 0; j < N; j++){
                if (j % 3 == 0) System.out.print("|");
                if (!visitados[i][j]) System.out.print(" F ");
                else System.out.print(" T ");
                if (j == N-1) System.out.print("|");
            }
            System.out.println();
            if (i == N-1) System.out.println("______________________________");
        }
    }
}
